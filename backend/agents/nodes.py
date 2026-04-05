from langchain_ollama import ChatOllama
from backend.config import OLLAMA_MODEL, OLLAMA_BASE_URL
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
llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1
)

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

    try:
        response = llm.invoke(prompt)
        state["planner_output"] = response.content
        print("[planner_node] Ollama planner succeeded.")
    except Exception as e:
        print(f"[planner_node] Ollama failed: {e}")
        state["planner_output"] = """
# Analysis Plan (Fallback)

1. Review dataset structure, schema, and datatypes.
2. Identify likely target candidates and validate ambiguity.
3. Assess missing values, duplicates, outliers, and leakage risks.
4. Compute KPIs and descriptive analytics.
5. Review signal ranking and correlations cautiously.
6. Generate business-relevant visualizations.
7. Assess ML readiness and preprocessing needs.
"""
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
# 9. Verifier Node (SAFE FALLBACK ADDED)
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

    try:
        response = llm.invoke(prompt)
        state["verifier_output"] = response.content
        print("[verifier_node] Ollama verifier succeeded.")
    except Exception as e:
        print(f"[verifier_node] Ollama failed: {e}")
        state["verifier_output"] = """
# Verification Report (Fallback)

## Analysis Priorities
- Focus on target validation, data quality, KPIs, signal ranking, and ML readiness.

## Validation Notes
- Results should be treated as exploratory unless explicitly model-validated.
- Signal ranking should not be interpreted as causality.

## Issues Found
- Manual review of target selection is recommended if multiple target candidates exist.

## Risks / Cautions
- Identifier-like fields, leakage, and outliers may distort findings.

## Recommendations
- Validate target manually, review preprocessing, and confirm business assumptions before modeling.
"""
    return state


# ============================================================
# 10. Final Report Node (SAFE FALLBACK ADDED)
# ============================================================
def final_report_node(state: AgentState) -> AgentState:
    target = state.get("target_validation_structured", {})
    dq = state.get("data_quality_structured", {})
    kpi = state.get("kpi_structured", {})
    sr = state.get("signal_ranking_structured", {})
    mlr = state.get("ml_readiness_structured", {})
    visualizations = state.get("visualizations", [])

    top_signals = sr.get("top_signals", [])[:5] if sr else []
    top_signal_lines = "\n".join(
        [f"- {item.get('feature')}: {item.get('importance')}" for item in top_signals]
    ) if top_signals else "- No structured signal ranking available"

    viz_lines = "\n".join(
        [f"- {v.get('title', 'Untitled')}: {v.get('interpretation', 'No interpretation')}" for v in visualizations[:5]]
    ) if visualizations else "- No visualizations generated"

    # ============================================================
    # STEP 1: Qwen (Ollama) creates the primary report
    # ============================================================
    base_prompt = f"""
You are a senior data analyst writing a polished executive analytics report.

Write ONLY the final markdown report.
Do NOT repeat the instructions.
Do NOT echo the prompt.

Use this exact structure:

# Final Report

## Executive Summary
## Target Validation
## Key Data Quality Findings
## Key Statistical / Analytical Findings
## KPI Highlights
## Signal Ranking Highlights
## Visualization Insights
## ML Readiness Assessment
## Risks / Cautions
## Actionable Recommendations
## Conclusion

DATASET:
- Filename: {state.get("filename", "N/A")}

TARGET:
- Selected Target: {target.get("target_column", "N/A")}
- Task Type: {target.get("task_type", "N/A")}
- Confidence: {target.get("confidence", "N/A")}
- Ambiguous: {target.get("ambiguous", False)}
- Note: {target.get("note", "N/A")}

DATA QUALITY:
- Quality Score: {dq.get("quality_score", "N/A")}
- Rows: {dq.get("rows", "N/A")}
- Columns: {dq.get("columns", "N/A")}
- Critical Issues: {dq.get("critical_issues", [])}
- Moderate Issues: {dq.get("moderate_issues", [])}
- Recommendations: {dq.get("recommendations", [])}

KPI:
- Domain: {kpi.get("domain", "N/A")}
- Metrics: {kpi.get("metrics", {})}

SIGNAL RANKING:
- Available: {sr.get("available", False)}
- Method: {sr.get("method", "N/A")}
- Top Signals:
{top_signal_lines}

VISUALIZATIONS:
{viz_lines}

ML READINESS:
- ML Ready: {mlr.get("is_ml_ready", "N/A")}
- Readiness Label: {mlr.get("readiness_label", "N/A")}
- Class Imbalance Flag: {mlr.get("class_imbalance_flag", "N/A")}
- Leakage Risk: {mlr.get("leakage_risk", [])}
- Preprocessing Recommendations: {mlr.get("preprocessing_recommendations", [])}
- Baseline Models: {mlr.get("baseline_model_suggestions", [])}

VERIFIER NOTES:
{state.get("verifier_output", "")[:1200]}

IMPORTANT RULES:
- Be accurate and conservative.
- Do NOT claim causality.
- If target is ambiguous, recommend manual confirmation.
- Use the term "Signal Ranking".
- If ML readiness is imperfect, say "Conditionally Ready" or "Requires preprocessing".
"""

    try:
        response = llm.invoke(base_prompt)
        base_report = response.content.strip()
        print("[final_report_node] Ollama Qwen base report succeeded.")
    except Exception as e:
        print(f"[final_report_node] Ollama failed: {e}")
        base_report = None

    # If Qwen failed, fallback hard
    if not base_report:
        state["final_report"] = """
# Final Report

## Executive Summary
- Automated analysis completed, but the final report generator encountered runtime issues.

## Target Validation
- Review the selected target manually if multiple candidate targets exist.

## Key Data Quality Findings
- Refer to the generated tool analysis and data quality outputs.

## Key Statistical / Analytical Findings
- Treat correlations and signal ranking as exploratory evidence only.

## KPI Highlights
- Review computed KPIs from the tool outputs.

## Signal Ranking Highlights
- Treat model-based signal ranking as directional, not causal.

## Visualization Insights
- Review generated charts carefully, especially identifier-like columns.

## ML Readiness Assessment
- Dataset may require preprocessing before production modeling.

## Risks / Cautions
- Final report generator fallback was triggered; verify conclusions manually.

## Actionable Recommendations
- Validate target, clean data, inspect leakage, and test baseline models.

## Conclusion
- Analysis completed with safeguards; results remain usable but should be reviewed.
"""
        return state

    # ============================================================
    # STEP 2: Fine-tuned model refines the Qwen report
    # ============================================================
    refine_prompt = f"""
You are a fine-tuned executive analytics report refiner.

Your task:
- Improve clarity
- Improve executive tone
- Make the report more concise and polished
- Preserve all factual meaning
- Do NOT add new claims
- Do NOT remove section headings
- Keep markdown structure intact

Here is the draft report:

{base_report}

Return ONLY the improved markdown report.
"""

    refined_report = query_finetuned_model(refine_prompt, max_new_tokens=320)

    if refined_report.startswith("[Fine-tuned model error]") or len(refined_report.strip()) < 200:
        print("[final_report_node] Fine-tuned refinement failed or too short. Using Qwen base report.")
        state["final_report"] = base_report
    else:
        print("[final_report_node] Fine-tuned refinement succeeded.")
        state["final_report"] = refined_report

    return state