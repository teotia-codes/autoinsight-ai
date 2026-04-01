from langgraph.graph import StateGraph, END
from backend.agents.state import AgentState
from backend.agents.nodes import (
    planner_node,
    tool_analysis_node,
    target_validation_node,
    data_quality_node,
    kpi_node,
    feature_importance_node,
    visualization_tool_node,
    ml_readiness_node,
    verifier_node,
    final_report_node,
)


def build_agent_graph():
    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("tool_analysis", tool_analysis_node)
    workflow.add_node("target_validation", target_validation_node)
    workflow.add_node("data_quality", data_quality_node)
    workflow.add_node("kpi", kpi_node)
    workflow.add_node("feature_importance", feature_importance_node)
    workflow.add_node("visualization_tool", visualization_tool_node)
    workflow.add_node("ml_readiness", ml_readiness_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("final_report", final_report_node)

    # Entry point
    workflow.set_entry_point("planner")

    # Phase 5 domain-agnostic flow
    workflow.add_edge("planner", "tool_analysis")
    workflow.add_edge("tool_analysis", "target_validation")
    workflow.add_edge("target_validation", "data_quality")
    workflow.add_edge("data_quality", "kpi")
    workflow.add_edge("kpi", "feature_importance")
    workflow.add_edge("feature_importance", "visualization_tool")
    workflow.add_edge("visualization_tool", "ml_readiness")
    workflow.add_edge("ml_readiness", "verifier")
    workflow.add_edge("verifier", "final_report")
    workflow.add_edge("final_report", END)

    return workflow.compile()