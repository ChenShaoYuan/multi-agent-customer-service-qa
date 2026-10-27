"""LangGraph state with isolated scoring branches and append-only trace reducers."""

import operator
from typing import Annotated, Literal, TypedDict


class AuditState(TypedDict, total=False):
    raw_input: dict
    audit_id: str
    ticket_id: str
    tag: str
    parent_tag: str
    messages: list[dict]
    role_source: Literal["provided", "inferred"]
    input_warnings: list[str]
    input_errors: list[str]
    preflight_report: dict
    redline_result: dict
    gate_status: Literal["pass", "blocked", "review"]
    service_process_result: dict
    professional_service_result: dict
    communication_result: dict
    node_traces: Annotated[list[dict], operator.add]
    technical_errors: Annotated[list[dict], operator.add]
    final_audit: dict
