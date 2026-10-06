"""Build the preserved week-two gate and the parallel week-three audit graph."""

from langgraph.graph import END, START, StateGraph

from customer_service_qa.agents import CriticalEvaluator, LiveCriticalEvaluator
from customer_service_qa.agents.dimensions import DimensionEvaluator, LiveDimensionEvaluator
from customer_service_qa.config import Settings
from customer_service_qa.graph.dimension_nodes import make_collect_node, make_dimension_node
from customer_service_qa.graph.nodes import (
    make_critical_node,
    make_final_nodes,
    make_normalize_node,
    make_preflight_node,
)
from customer_service_qa.schemas.scoring import DIMENSIONS, DimensionName
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


def build_week3_graph(
    critical_evaluator: CriticalEvaluator | None = None,
    dimension_evaluators: dict[DimensionName, DimensionEvaluator] | None = None,
    settings: Settings | None = None,
):
    settings = settings or Settings()
    critical_evaluator = critical_evaluator or LiveCriticalEvaluator(settings)
    dimension_evaluators = dimension_evaluators or {}
    unknown = set(dimension_evaluators) - set(DIMENSIONS)
    if unknown:
        raise ValueError(f"Unknown dimensions: {sorted(unknown)}")
    builder = StateGraph(AuditState)
    builder.add_node("normalize_input", make_normalize_node(settings))
    builder.add_node("preflight", make_preflight_node(settings))
    builder.add_node("critical_gate", make_critical_node(settings, critical_evaluator))
    final_nodes = make_final_nodes(settings)
    for name in ("blocked_result", "manual_review_result"):
        builder.add_node(name, final_nodes[name])
        builder.add_edge(name, END)
    for dimension in DIMENSIONS:
        builder.add_node(
            dimension,
            make_dimension_node(
                dimension,
                settings,
                dimension_evaluators.get(dimension) or LiveDimensionEvaluator(settings),
            ),
        )
    builder.add_node("collect_dimensions", make_collect_node(settings))
    builder.add_edge(START, "normalize_input")
    builder.add_edge("normalize_input", "preflight")
    builder.add_edge("preflight", "critical_gate")

    def route(state):
        gate = route_after_critical(state)
        return (
            list(DIMENSIONS)
            if gate == "pass"
            else {"blocked": "blocked_result", "review": "manual_review_result"}[gate]
        )

    builder.add_conditional_edges(
        "critical_gate",
        route,
        [*DIMENSIONS, "blocked_result", "manual_review_result"],
    )
    # One list edge is a barrier: collect only after all three branches finish.
    builder.add_edge(list(DIMENSIONS), "collect_dimensions")
    builder.add_edge("collect_dimensions", END)
    return builder.compile()
