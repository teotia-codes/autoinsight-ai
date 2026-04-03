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
   - signal ranking
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
    ambiguous = target_info.get("ambiguous", False)
    alternate_targets = target_info.get("alternate_targets", [])
    note = target_info.get("note", "")

    lines.append(f"Selected Target Column: {target_col}")
    lines.append(f"Task Type: {task_type}")
    lines.append(f"Confidence: {confidence}")
    lines.append(f"Ambiguous Target: {ambiguous}")

    if alternate_targets:
        lines.append(f"Alternate Targets: {alternate_targets}")

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
# 6. Signal Ranking Node
# ============================================================
def signal_ranking_node(state: AgentState) -> AgentState:
    sr = state.get("tool_analysis_result", {}).get("signal_ranking", {})

    lines = []
    lines.append("SIGNAL RANKING AGENT REPORT")
    lines.append("=" * 50)

    if sr.get("available", False):
        lines.append(f"Target Used: {sr.get('target_column', None)}")
        lines.append(f"Task Type: {sr.get('task_type', 'unknown')}")
        lines.append(f"Method: {sr.get('method', 'unknown')}")
        lines.append("Top Signals:")

        for feat in sr.get("top_signals", []):
            lines.append(f"- {feat['feature']}: {feat['importance']}")
    else:
        lines.append(f"Signal ranking unavailable: {sr.get('reason', 'Unknown reason')}")

    state["signal_ranking_output"] = "\n".join(lines)
    state["signal_ranking_structured"] = sr
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
# 9. Verifier Node (UPDATED)
# ============================================================
def verifier_node(state: AgentState) -> AgentState:
    prompt = f"""
You are a strict senior data analyst and QA reviewer.

Your job is to VERIFY the analytical correctness of the generated analysis.
You must:
1. Identify weak claims, overstatements, or unsupported conclusions.
2. Check whether the selected target is ambiguous.
3. Distinguish between exploratory signals and true model-based signal ranking.
4. Highlight any suspicious visualization choices.
5. Avoid repeating the entire report. Focus on critique, caveats, and validation notes only.

ANALYSIS PRIORITIES:
{state.get("planner_output", "")}

STRUCTURED ANALYSIS EVIDENCE:
Tool Analysis:
{state.get("tool_analysis_text", "")}

Target Validation:
{state.get("target_validation_output", "")}

Data Quality:
{state.get("data_quality_output", "")}

KPI Summary:
{state.get("kpi_output", "")}

Signal Ranking:
{state.get("signal_ranking_output", "")}

Visualization Summary:
{state.get("visualization_summary", "")}

ML Readiness:
{state.get("ml_readiness_output", "")}

Retrieved Business Context:
{state.get("retrieved_context", "N/A")}

Important rules:
- If the target analysis says ambiguous=true, explicitly say the target should be manually confirmed.
- If signals are derived from Random Forest, call them "model-based signal ranking".
- Do NOT call signal ranking causal proof.
- If any identifier-like or postal/zip/code-like columns are used in charts, flag them as weak chart choices.
- Keep output concise and practical.

Return:
- Analysis Priorities
- Validation Notes
- Issues Found
- Risks / Cautions
- Recommendations

Return a concise, evidence-grounded verification report in markdown.
"""

    response = llm.invoke(prompt)
    state["verifier_output"] = response.content
    return state


# ============================================================
# 10. Final Report Node (UPDATED)
# ============================================================
def final_report_node(state: AgentState) -> AgentState:
    prompt = f"""
You are a senior data analyst writing a polished executive analytics report.

Create a FINAL REPORT using the evidence below.

IMPORTANT RULES:
1. Be accurate and conservative. Do NOT exaggerate.
2. If target selection is ambiguous, explicitly mention that the selected target is the default choice and manual confirmation is recommended.
3. Use the term "Signal Ranking" instead of "Feature Importance".
4. If ML readiness is not fully clean, say "Conditionally Ready" or "Requires preprocessing" instead of claiming the dataset is fully ready.
5. Do NOT repeat the verification section verbatim.
6. Keep the report executive, analytical, and grounded.
7. Do NOT claim causality from correlations or model-based signal ranking.

INPUTS:

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

Signal Ranking:
{state.get("signal_ranking_output", "N/A")}

Visualization Summary:
{state.get("visualization_summary", "N/A")}

ML Readiness:
{state.get("ml_readiness_output", "N/A")}

Verifier:
{state.get("verifier_output", "N/A")}

Retrieved Business Context:
{state.get("retrieved_context", "N/A")}

Write the report in markdown with this exact structure:

# Final Report

## Executive Summary
- concise business + analytical summary

## Target Validation
- selected target
- task type
- confidence
- if ambiguous, mention alternate targets and recommend manual confirmation

## Key Data Quality Findings
- missingness
- duplicates
- outliers
- identifier-like columns / leakage risks

## Key Statistical / Analytical Findings
- correlations
- distribution / trends
- important exploratory observations

## KPI Highlights
- include computed KPIs only if supported by evidence

## Signal Ranking Highlights
- summarize the top model-based signals
- do NOT overclaim causality

## Visualization Insights
- summarize what the generated charts reveal
- mention if any chart recommendations should be interpreted cautiously

## ML Readiness Assessment
- readiness label
- preprocessing needs
- baseline models

## Risks / Cautions
- explicit caveats

## Actionable Recommendations
- practical next steps

## Conclusion
- short, grounded conclusion
"""

    response = llm.invoke(prompt)
    state["final_report"] = response.content
    return state