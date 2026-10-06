"""Complete graph with protected boundaries and a ReAct aggregation node."""

from datetime import UTC, datetime
from time import perf_counter

from langgraph.graph import END, START, StateGraph

from customer_service_qa.agents import LiveCriticalEvaluator
from customer_service_qa.agents.dimensions import LiveDimensionEvaluator
from customer_service_qa.agents.summary_agent import LiveSummaryPlanner, run_summary_agent
from customer_service_qa.config import Settings
from customer_service_qa.graph.dimension_nodes import make_dimension_node
from customer_service_qa.graph.nodes import (
    _trace,
    make_critical_node,
    make_normalize_node,
    make_preflight_node,
)
from customer_service_qa.schemas.audit import Alert, FinalAudit
from customer_service_qa.schemas.scoring import DIMENSIONS
from customer_service_qa.schemas.state import AuditState
from customer_service_qa.summary import prepare_audit


def guarded_node(name, node, settings):
    def run(state):
        started, counter = datetime.now(UTC), perf_counter()
        try:
            return node(state)
        except Exception as error:
            updates = {
                "technical_errors": [
                    {
                        "node": name,
                        "attempt": 1,
                        "error_type": type(error).__name__,
                        "message": "节点异常，已转人工复核。",
                    }
                ],
                "node_traces": [_trace(name, "error", started, counter, settings)],
            }
            if name == "normalize_input":
                updates.update(
                    ticket_id="",
                    tag="",
                    parent_tag="",
                    messages=[],
                    role_source="provided",
                    input_errors=["input_normalization_failed"],
                )
            elif name == "preflight":
                updates["preflight_report"] = None
            else:
                updates.update(gate_status="review", redline_result=None)
            return updates

    return run


def make_summary_node(settings, planner):
    def summarize(state):
        started, counter = datetime.now(UTC), perf_counter()
        prepared = prepare_audit(state)
        try:
            result = run_summary_agent(prepared, planner, settings.summary_max_steps)
        except Exception as error:
            result = prepared.model_copy(deep=True)
            result.status, result.grade, result.total_score = "manual_review", "待人工复核", None
            result.manual_review_reasons.append("汇总遇到未预期错误。")
            result.alerts.append(
                Alert(
                    code="SUMMARY_ERROR",
                    severity="error",
                    node="summary_agent",
                    message="汇总失败，未生成业务总分。",
                )
            )
            result.technical_errors.append(
                {"node": "summary_agent", "error_type": type(error).__name__, "message": "汇总失败"}
            )
        trace = _trace(
            "summary_agent",
            "error" if result.status == "manual_review" else "success",
            started,
            counter,
            settings,
            details={"status": result.status, "tool_steps": len(result.react_steps)},
        )
        result.trace.append(trace)
        final = FinalAudit.model_validate(result.model_dump()).model_dump(mode="json")
        return {"final_audit": final, "node_traces": [trace]}

    return summarize


def build_week4_graph(
    critical_evaluator=None,
    dimension_evaluators=None,
    summary_planner=None,
    settings=None,
    rule_lookup=None,
):
    settings = settings or Settings()
    dimension_evaluators = dimension_evaluators or {}
    if set(dimension_evaluators) - set(DIMENSIONS):
        raise ValueError("Unknown dimension evaluators")
    builder = StateGraph(AuditState)
    nodes = {
        "normalize_input": make_normalize_node(settings),
        "preflight": make_preflight_node(settings),
        "critical_gate": make_critical_node(
            settings, critical_evaluator or LiveCriticalEvaluator(settings)
        ),
    }
    for name, node in nodes.items():
        builder.add_node(name, guarded_node(name, node, settings))
    for name in DIMENSIONS:
        builder.add_node(
            name,
            make_dimension_node(
                name,
                settings,
                dimension_evaluators.get(name) or LiveDimensionEvaluator(settings),
                rule_lookup=rule_lookup,
            ),
        )
    builder.add_node(
        "summary_agent",
        make_summary_node(settings, summary_planner or LiveSummaryPlanner(settings)),
    )
    builder.add_edge(START, "normalize_input")
    builder.add_edge("normalize_input", "preflight")
    builder.add_edge("preflight", "critical_gate")
    builder.add_conditional_edges(
        "critical_gate",
        lambda s: list(DIMENSIONS) if s.get("gate_status") == "pass" else "summary_agent",
        [*DIMENSIONS, "summary_agent"],
    )
    builder.add_edge(list(DIMENSIONS), "summary_agent")
    builder.add_edge("summary_agent", END)
    return builder.compile()
