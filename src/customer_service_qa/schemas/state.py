"""LangGraph shared state for the week-two workflow."""

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
    node_traces: Annotated[list[dict], operator.add]
    technical_errors: Annotated[list[dict], operator.add]
    final_audit: dict
