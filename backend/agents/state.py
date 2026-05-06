from typing import TypedDict, Dict, Any, List, Optional


class AgentState(TypedDict):
    # Input
    filename: str
    file_path: str
    summary_text: str

    # RAG / Planner
    retrieved_context: str
    planner_output: str

    # Tool analysis
    tool_analysis_result: Dict[str, Any]
    tool_analysis_text: str

    # ── NEW: records which branch the router chose ──────────────
    route_taken: str   # "eda_only" | "full" | "ml_heavy"
    # ────────────────────────────────────────────────────────────

    # Target Validation Agent
    target_validation_output: str
    target_validation_structured: Dict[str, Any]

    # Data Quality Agent
    data_quality_output: str
    data_quality_structured: Dict[str, Any]

    # KPI Agent
    kpi_output: str
    kpi_structured: Dict[str, Any]

    # Feature Importance Agent
    feature_importance_output: str
    feature_importance_structured: Dict[str, Any]

    # Visualization Agent
    visualizations: List[Dict[str, Any]]
    chart_paths: List[str]
    visualization_summary: str

    # ML Readiness Agent
    ml_readiness_output: str
    ml_readiness_structured: Dict[str, Any]

    # Signal Ranking (explicit field — was missing from original state)
    signal_ranking_output: str
    signal_ranking_structured: Dict[str, Any]

    # Verifier + Final
    verifier_output: str
    final_report: str