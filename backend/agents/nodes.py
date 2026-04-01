from langchain_ollama import ChatOllama

from backend.agents.state import AgentState
from backend.tools.analysis_tools import (
    run_real_data_analysis,
    build_tool_analysis_text,
    build_data_quality_report,
    build_data_quality_text,
    build_kpi_report,
    build_kpi_text,
    build_ml_readiness_report,
    build_ml_readiness_text,
)
from backend.tools.visualization_tools import generate_recommended_visualizations
from backend.rag.retrieve import retrieve_relevant_context

# Local LLM via Ollama
llm = ChatOllama(model="qwen2.5:3b", temperature=0.1)


# ============================================================
# 1. Planner Node
# ============================================================
def planner_node(state: AgentState) -> AgentState:
    context = retrieve_relevant_context(state["summary_text"], k=3)
    state["retrieved_context"] = context

    prompt = f"""
You are the PLANNER AGENT for an autonomous analytics system.

Dataset Summary:
{state["summary_text"]}

Retrieved Business / Domain Context:
{context}

Your job:
1. Identify the likely analysis priorities.
2. Mention what business / domain questions matter most.
3. Suggest what should be checked:
   - target validity
   - data quality
   - correlations
   - outliers
   - KPIs
   - feature importance
   - ML readiness
   - visualizations
4. Keep the plan concise, structured, and domain-aware.
5. Do NOT make unsupported claims.
"""

    response = llm.invoke(prompt)
    state["planner_output"] = response.content
    return state


# ============================================================
# 2. Tool Analysis Node
# ============================================================
def tool_analysis_node(state: AgentState) -> AgentState:
    analysis_result = run_real_data_analysis(state["file_path"])
    analysis_text = build_tool_analysis_text(analysis_result)

    state["tool_analysis_result"] = analysis_result
    state["tool_analysis_text"] = analysis_text
    return state


# ============================================================
# 3. Target Validation Node
# ============================================================
def target_validation_node(state: AgentState) -> AgentState:
    target_info = state.get("tool_analysis_result", {}).get("target_analysis", {})

    lines = []
    lines.append("TARGET VALIDATION AGENT REPORT")
    lines.append("=" * 50)

    target_col = target_info.get("target_column")
    task_type = target_info.get("task_type", "unknown")
    confidence = target_info.get("confidence", "low")
    note = target_info.get("note", "")

    lines.append(f"Selected Target Column: {target_col}")
    lines.append(f"Task Type: {task_type}")
    lines.append(f"Confidence: {confidence}")
    lines.append(f"Selection Note: {note}")
    lines.append("")

    candidates = target_info.get("candidates", [])
    if candidates:
        lines.append("Top Candidate Targets:")
        for c in candidates[:5]:
            reasons = ", ".join(c.get("reasons", []))
            lines.append(
                f"- {c.get('column')} | score={c.get('score')} | "
                f"nunique={c.get('nunique')} | dtype={c.get('dtype')} | reasons={reasons}"
            )
    else:
        lines.append("No strong target candidates found.")

    state["target_validation_output"] = "\n".join(lines)
    state["target_validation_structured"] = target_info
    return state


# ============================================================
# 4. Data Quality Node
# ============================================================
def data_quality_node(state: AgentState) -> AgentState:
    analysis_result = state.get("tool_analysis_result", {})
    dq = build_data_quality_report(analysis_result)
    dq_text = build_data_quality_text(dq)

    state["data_quality_structured"] = dq
    state["data_quality_output"] = dq_text
    return state


# ============================================================
# 5. KPI Node
# ============================================================
def kpi_node(state: AgentState) -> AgentState:
    analysis_result = state.get("tool_analysis_result", {})
    kpi = build_kpi_report(state["file_path"], analysis_result)
    kpi_text = build_kpi_text(kpi)

    state["kpi_structured"] = kpi
    state["kpi_output"] = kpi_text
    return state


# ============================================================
# 6. Feature Importance Node
# ============================================================
def feature_importance_node(state: AgentState) -> AgentState:
    fi = state.get("tool_analysis_result", {}).get("feature_importance", {})

    lines = []
    lines.append("FEATURE IMPORTANCE AGENT REPORT")
    lines.append("=" * 50)

    if fi.get("available", False):
        lines.append(f"Target Used: {fi.get('target_column', None)}")
        lines.append(f"Task Type: {fi.get('task_type', 'unknown')}")
        lines.append("Top Predictors:")

        for feat in fi.get("top_features", []):
            lines.append(f"- {feat['feature']}: {feat['importance']}")
    else:
        lines.append(f"Feature importance unavailable: {fi.get('reason', 'Unknown reason')}")

    state["feature_importance_output"] = "\n".join(lines)
    state["feature_importance_structured"] = fi
    return state


# ============================================================
# 7. Visualization Tool Node
# ============================================================
def visualization_tool_node(state: AgentState) -> AgentState:
    analysis_result = state.get("tool_analysis_result", {})

    visualizations = generate_recommended_visualizations(
        file_path=state["file_path"],
        analysis_result=analysis_result
    )

    chart_paths = [viz["path"] for viz in visualizations if "path" in viz]

    summary_lines = []
    summary_lines.append("AUTONOMOUS VISUALIZATION AGENT REPORT")

    if visualizations:
        for viz in visualizations:
            summary_lines.append(f"- {viz.get('title', 'Untitled')}")
            summary_lines.append(f"  Type: {viz.get('chart_type', 'N/A')}")
            summary_lines.append(f"  Columns: {viz.get('columns', [])}")
            summary_lines.append(f"  Interpretation: {viz.get('interpretation', 'No interpretation')}")
    else:
        summary_lines.append("- No suitable visualizations generated.")

    state["visualizations"] = visualizations
    state["chart_paths"] = chart_paths
    state["visualization_summary"] = "\n".join(summary_lines)
    return state


# ============================================================
# 8. ML Readiness Node
# ============================================================
def ml_readiness_node(state: AgentState) -> AgentState:
    analysis_result = state.get("tool_analysis_result", {})
    mlr = build_ml_readiness_report(analysis_result)
    mlr_text = build_ml_readiness_text(mlr)

    state["ml_readiness_structured"] = mlr
    state["ml_readiness_output"] = mlr_text
    return state


# ============================================================
# 9. Verifier Node (Evidence-grounded)
# ============================================================
def verifier_node(state: AgentState) -> AgentState:
    prompt = f"""
You are the VERIFIER AGENT in an autonomous analytics system.

STRICT RULES:
1. Do NOT exaggerate evidence.
2. Do NOT call weak correlations "strong".
3. Do NOT invent causal claims.
4. Only use information explicitly present in the provided inputs.
5. If evidence is weak, say it is weak / preliminary / requires validation.
6. If target detection confidence is low, explicitly mention that.
7. If feature importance is unavailable, mention that this limits confidence.

Your task:
- Check consistency across all analysis outputs
- Identify unsupported or exaggerated claims
- Identify risks or weak conclusions
- Confirm what appears strongly supported
- Mention where manual validation is recommended

Planner Output:
{state.get("planner_output", "N/A")}

Tool-Based Analysis:
{state.get("tool_analysis_text", "N/A")}

Target Validation:
{state.get("target_validation_output", "N/A")}

Data Quality Report:
{state.get("data_quality_output", "N/A")}

KPI Report:
{state.get("kpi_output", "N/A")}

Feature Importance:
{state.get("feature_importance_output", "N/A")}

Visualization Summary:
{state.get("visualization_summary", "N/A")}

ML Readiness Report:
{state.get("ml_readiness_output", "N/A")}

Retrieved Business Context:
{state.get("retrieved_context", "N/A")}

Return a concise, evidence-grounded verification report in markdown.
"""

    response = llm.invoke(prompt)
    state["verifier_output"] = response.content
    return state


# ============================================================
# 10. Final Report Node (No-hallucination)
# ============================================================
def final_report_node(state: AgentState) -> AgentState:
    prompt = f"""
You are the FINAL REPORT AGENT for AutoInsight AI.

You must produce a polished, professional, executive-style final report.

STRICT EVIDENCE RULES:
1. Only use facts explicitly supported by the inputs below.
2. Do NOT exaggerate weak evidence.
3. If a correlation is weak, describe it as weak.
4. Do NOT claim causation from correlation.
5. If target detection confidence is low or medium, clearly mention manual validation is recommended.
6. If feature importance is unavailable, state that predictive ranking is limited.
7. If the dataset is not ML-ready, say so clearly.
8. Be domain-aware, but do NOT invent domain-specific claims not supported by the data.

Required sections:
1. Executive Summary
2. Target Validation
3. Key Data Quality Findings
4. Key Statistical / Analytical Findings
5. KPI Highlights
6. Feature Importance Highlights
7. Visualization Insights
8. ML Readiness Assessment
9. Risks / Cautions
10. Actionable Recommendations

Inputs:

Planner Output:
{state.get("planner_output", "N/A")}

Tool Analysis:
{state.get("tool_analysis_text", "N/A")}

Target Validation:
{state.get("target_validation_output", "N/A")}

Data Quality:
{state.get("data_quality_output", "N/A")}

KPI:
{state.get("kpi_output", "N/A")}

Feature Importance:
{state.get("feature_importance_output", "N/A")}

Visualization Summary:
{state.get("visualization_summary", "N/A")}

ML Readiness:
{state.get("ml_readiness_output", "N/A")}

Verifier:
{state.get("verifier_output", "N/A")}

Retrieved Business Context:
{state.get("retrieved_context", "N/A")}

Write the report in markdown.
"""

    response = llm.invoke(prompt)
    state["final_report"] = response.content
    return state