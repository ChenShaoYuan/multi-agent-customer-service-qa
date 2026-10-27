"""Pydantic models for normalized input, preflight facts, and redline results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["end-user", "agent", "system"]
GateStatus = Literal["pass", "blocked", "review"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    role: MessageRole
    content: str = Field(min_length=1)
    timestamp: datetime | None = None


class NormalizedConversation(BaseModel):
    ticket_id: str
    tag: str
    parent_tag: str
    messages: list[Message]
    role_source: Literal["provided", "inferred"]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ConversationStats(BaseModel):
    message_count: int = 0
    user_count: int = 0
    agent_count: int = 0
    system_count: int = 0
    turn_count: int = 0


class PresenceCheck(BaseModel):
    evaluable: bool = True
    present: bool | None = None
    message_id: str | None = None


class TimingViolation(BaseModel):
    user_message_id: str
    agent_message_id: str
    elapsed_seconds: float


class KeywordHit(BaseModel):
    rule_id: str
    keyword: str
    message_id: str
    context: str


class SensitiveDataHit(BaseModel):
    kind: str
    message_id: str
    masked_value: str


class TransferEvent(BaseModel):
    message_id: str
    role: MessageRole
    content: str


class PreflightReport(BaseModel):
    input_valid: bool
    input_errors: list[str] = Field(default_factory=list)
    role_source: Literal["provided", "inferred"]
    timing_available: bool
    timing_errors: list[str] = Field(default_factory=list)
    conversation_stats: ConversationStats
    greeting: PresenceCheck
    closing: PresenceCheck
    first_response_seconds: float | None = None
    first_response_evaluable: bool = False
    first_response_violation: bool | None = None
    response_time_violations: list[TimingViolation] = Field(default_factory=list)
    redline_keyword_hits: list[KeywordHit] = Field(default_factory=list)
    sensitive_data_hits: list[SensitiveDataHit] = Field(default_factory=list)
    tag_warnings: list[str] = Field(default_factory=list)
    repeated_reply_message_ids: list[list[str]] = Field(default_factory=list)
    transfer_events: list[TransferEvent] = Field(default_factory=list)


class RedlineFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: Literal["CR-01", "CR-02", "CR-03", "CR-04"]
    triggered: bool
    reason: str = Field(min_length=1)
    evidence_message_ids: list[str] = Field(default_factory=list)


class RedlineAssessment(BaseModel):
    """The schema requested from the LLM before deterministic validation."""

    model_config = ConfigDict(extra="forbid")

    items: list[RedlineFinding]
    summary: str = Field(min_length=1)


class RedlineResult(BaseModel):
    items: list[RedlineFinding] = Field(default_factory=list)
    triggered: bool
    gate_status: GateStatus
    summary: str


class NodeTrace(BaseModel):
    node: str
    status: Literal["success", "skipped", "error"]
    started_at: datetime
    duration_ms: float = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    rule_version: str
    prompt_version: str
    model_name: str | None = None
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
