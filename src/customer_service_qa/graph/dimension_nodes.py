"""Independent score branches and a week-three join (no weighted final grade yet)."""

from datetime import UTC, datetime
from time import perf_counter

from customer_service_qa.agents.dimensions import (
    build_dimension_context,
    evaluate_dimension,
    failed_dimension,
)
from customer_service_qa.graph.nodes import _trace
from customer_service_qa.schemas import NormalizedConversation, PreflightReport
from customer_service_qa.schemas.scoring import DIMENSIONS, DimensionResult
from customer_service_qa.tools.professional_rules import UnknownCategoryError
from customer_service_qa.tools.rule_gateway import get_rule_lookup


def make_dimension_node(dimension, settings, evaluator, rule_lookup=None):
    def dimension_node(state):
        started_at, started_counter = datetime.now(UTC), perf_counter()
        tool_trace = []
        try:
            conversation = NormalizedConversation(
                ticket_id=state["ticket_id"],
                tag=state["tag"],
                parent_tag=state["parent_tag"],
                messages=state["messages"],
                role_source=state["role_source"],
                warnings=state.get("input_warnings", []),
                errors=state.get("input_errors", []),
            )
            context = build_dimension_context(
                dimension,
                conversation,
                PreflightReport.model_validate(state["preflight_report"]),
                rule_lookup=rule_lookup or get_rule_lookup(settings),
            )
            if context.professional_rules:
                bundle = context.professional_rules
                tool_trace.append(
                    {
                        "tool": "get_professional_rules",
                        "status": "success",
                        "source": bundle.source,
                        "version": bundle.version,
                        "rule_count": len(bundle.rules),
                        "transport": settings.rules_transport,
                    }
                )
            result = evaluate_dimension(context, evaluator)
        except UnknownCategoryError:
            tool_trace.append({"tool": "get_professional_rules", "status": "not_found"})
            result = failed_dimension(
                dimension, "一级标签不在规则库中，需确认标签后重跑。", status="manual_review"
            )
        except Exception as error:
            # Catch within each branch: keep completed siblings when a tool/node fails.
            result = failed_dimension(
                dimension,
                "评分上下文或规则工具异常，请人工复核。",
                errors=[
                    {
                        "node": dimension,
                        "attempt": 0,
                        "error_type": type(error).__name__,
                        "message": "评分上下文或规则工具异常",
                    }
                ],
            )
        result.tool_trace = tool_trace
        trace = _trace(
            dimension,
            "success" if result.status in ("completed", "partial") else "error",
            started_at,
            started_counter,
            settings,
            retry_count=max(0, result.attempts - 1),
            details={
                "result_status": result.status,
                "attempts": result.attempts,
                "rule_lookup_status": tool_trace[0]["status"] if tool_trace else None,
            },
        )
        return {
            f"{dimension}_result": result.model_dump(mode="json"),
            "node_traces": [trace],
            "technical_errors": result.errors,
        }

    return dimension_node


def make_collect_node(settings):
    def collect_dimensions(state):
        started_at, started_counter = datetime.now(UTC), perf_counter()
        dimensions = {
            name: DimensionResult.model_validate(state[f"{name}_result"]) for name in DIMENSIONS
        }
        needs_review = any(result.status != "completed" for result in dimensions.values())
        trace = _trace("collect_dimensions", "success", started_at, started_counter, settings)
        final_audit = {
            "audit_id": state["audit_id"],
            "ticket_id": state["ticket_id"],
            "week": 3,
            "status": "manual_review" if needs_review else "dimensions_completed",
            "grade": "待人工复核" if needs_review else "待第四周汇总",
            "total_score": None,
            "redline": state["redline_result"],
            "preflight": state["preflight_report"],
            "dimensions": {
                name: result.model_dump(mode="json") for name, result in dimensions.items()
            },
            "ready_for_summary": not needs_review,
            "manual_review_reasons": [
                f"{name}: {reason}"
                for name, result in dimensions.items()
                for reason in result.review_reasons
            ],
            "technical_errors": state.get("technical_errors", []),
            "trace": [*state.get("node_traces", []), trace],
        }
        return {"final_audit": final_audit, "node_traces": [trace]}

    return collect_dimensions
