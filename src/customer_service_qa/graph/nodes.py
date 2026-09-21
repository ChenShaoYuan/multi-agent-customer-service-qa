"""Node implementations for normalization, preflight, redline, and week-two results."""

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from customer_service_qa.adapters import normalize_input
from customer_service_qa.agents import CriticalEvaluator, evaluate_redlines
from customer_service_qa.config import Settings
from customer_service_qa.preflight import run_preflight
from customer_service_qa.schemas import Message, NodeTrace, NormalizedConversation, PreflightReport
from customer_service_qa.schemas.state import AuditState


def _trace(
    node: str,
    status: str,
    started_at: datetime,
    started_counter: float,
    settings: Settings,
    *,
    retry_count: int = 0,
    details: dict | None = None,
) -> dict:
    return NodeTrace(
        node=node,
        status=status,
        started_at=started_at,
        duration_ms=round((perf_counter() - started_counter) * 1000, 3),
        retry_count=retry_count,
        rule_version=settings.rule_version,
        prompt_version=settings.prompt_version,
        model_name=settings.llm_model if node == "critical_gate" else None,
        details=details or {},
    ).model_dump(mode="json")


def make_normalize_node(settings: Settings) -> Callable[[AuditState], dict]:
    def normalize_node(state: AuditState) -> dict:
        started_at = datetime.now(UTC)
        started_counter = perf_counter()
        conversation = normalize_input(state.get("raw_input", {}))
        trace = _trace(
            "normalize_input",
            "success" if not conversation.errors else "error",
            started_at,
            started_counter,
            settings,
            details={"message_count": len(conversation.messages)},
        )
        return {
            "audit_id": state.get("audit_id") or str(uuid4()),
            "ticket_id": conversation.ticket_id,
            "tag": conversation.tag,
            "parent_tag": conversation.parent_tag,
            "messages": [message.model_dump(mode="json") for message in conversation.messages],
            "role_source": conversation.role_source,
            "input_warnings": conversation.warnings,
            "input_errors": conversation.errors,
            "node_traces": [trace],
        }

    return normalize_node


def make_preflight_node(settings: Settings) -> Callable[[AuditState], dict]:
    def preflight_node(state: AuditState) -> dict:
        started_at = datetime.now(UTC)
        started_counter = perf_counter()
        conversation = NormalizedConversation(
            ticket_id=state.get("ticket_id", ""),
            tag=state.get("tag", ""),
            parent_tag=state.get("parent_tag", ""),
            messages=[Message.model_validate(message) for message in state.get("messages", [])],
            role_source=state.get("role_source", "inferred"),
            warnings=state.get("input_warnings", []),
            errors=state.get("input_errors", []),
        )
        report = run_preflight(conversation)
        trace = _trace(
            "preflight",
            "success" if report.input_valid else "error",
            started_at,
            started_counter,
            settings,
            details={"input_valid": report.input_valid},
        )
        return {
            "preflight_report": report.model_dump(mode="json"),
            "node_traces": [trace],
        }

    return preflight_node


def make_critical_node(
    settings: Settings, evaluator: CriticalEvaluator
) -> Callable[[AuditState], dict]:
    def critical_node(state: AuditState) -> dict:
        started_at = datetime.now(UTC)
        started_counter = perf_counter()
        messages = [Message.model_validate(message) for message in state.get("messages", [])]
        preflight = PreflightReport.model_validate(state["preflight_report"])
        result, errors = evaluate_redlines(messages, preflight, evaluator)
        trace = _trace(
            "critical_gate",
            "error" if result.gate_status == "review" else "success",
            started_at,
            started_counter,
            settings,
            retry_count=max(0, len(errors) - 1),
            details={"gate_status": result.gate_status},
        )
        return {
            "redline_result": result.model_dump(mode="json"),
            "gate_status": result.gate_status,
            "technical_errors": errors,
            "node_traces": [trace],
        }

    return critical_node


def _final_node(
    status: str,
    grade: str,
    settings: Settings,
) -> Callable[[AuditState], dict]:
    def finalize(state: AuditState) -> dict:
        started_at = datetime.now(UTC)
        started_counter = perf_counter()
        trace = _trace(
            f"finalize_{status}",
            "success",
            started_at,
            started_counter,
            settings,
        )
        review_reasons = [error["message"] for error in state.get("technical_errors", [])]
        review_reasons.extend(state.get("input_errors", []))
        final_audit = {
            "audit_id": state.get("audit_id"),
            "ticket_id": state.get("ticket_id"),
            "status": status,
            "grade": grade,
            "redline": state.get("redline_result"),
            "preflight": state.get("preflight_report"),
            "ready_for_dimension_audit": status == "ready_for_dimension_audit",
            "manual_review_reasons": list(dict.fromkeys(review_reasons)),
            "trace": [*state.get("node_traces", []), trace],
        }
        return {"final_audit": final_audit, "node_traces": [trace]}

    return finalize


def make_final_nodes(settings: Settings) -> dict[str, Callable[[AuditState], dict]]:
    return {
        "blocked_result": _final_node("blocked", "严重不合格", settings),
        "manual_review_result": _final_node("manual_review", "待人工复核", settings),
        "ready_result": _final_node(
            "ready_for_dimension_audit", "待三维评分", settings
        ),
    }
