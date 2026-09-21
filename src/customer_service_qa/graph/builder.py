"""Build the executable week-two LangGraph."""

from langgraph.graph import END, START, StateGraph

from customer_service_qa.agents import CriticalEvaluator, LiveCriticalEvaluator
from customer_service_qa.config import Settings
from customer_service_qa.graph.nodes import (
    make_critical_node,
    make_final_nodes,
    make_normalize_node,
    make_preflight_node,
)
from customer_service_qa.schemas.state import AuditState


def route_after_critical(state: AuditState) -> str:
    return state.get("gate_status", "review")


def build_week2_graph(
    evaluator: CriticalEvaluator | None = None,
    settings: Settings | None = None,
):
    settings = settings or Settings()
    evaluator = evaluator or LiveCriticalEvaluator(settings)
    final_nodes = make_final_nodes(settings)

    builder = StateGraph(AuditState)
    builder.add_node("normalize_input", make_normalize_node(settings))
    builder.add_node("preflight", make_preflight_node(settings))
    builder.add_node("critical_gate", make_critical_node(settings, evaluator))
    for name, node in final_nodes.items():
        builder.add_node(name, node)

    builder.add_edge(START, "normalize_input")
    builder.add_edge("normalize_input", "preflight")
    builder.add_edge("preflight", "critical_gate")
    builder.add_conditional_edges(
        "critical_gate",
        route_after_critical,
        {
            "blocked": "blocked_result",
            "review": "manual_review_result",
            "pass": "ready_result",
        },
    )
    builder.add_edge("blocked_result", END)
    builder.add_edge("manual_review_result", END)
    builder.add_edge("ready_result", END)
    return builder.compile()
