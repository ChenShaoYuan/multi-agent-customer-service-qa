"""Stable final contract for completed, redline and technical-review paths."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from customer_service_qa.schemas.scoring import DimensionResult, Evidence


class Alert(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    node: str
    message: str


class Finding(BaseModel):
    finding_id: str
    issue_id: str
    dimension: str
    item_id: str
    deduction: int
    weighted_deduction: float
    reason: str
    rule_ids: list[str]
    rule_texts: list[str]
    evidence: list[Evidence]
    mergeable: bool


class DuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_ids: list[str] = Field(min_length=2)
    reason: str = Field(min_length=10, description="简述为何属于同一业务问题，而非仅同一句话。")
    evidence_message_ids: list[str] = Field(min_length=1)


class FinalizeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duplicate_groups: list[DuplicateGroup]
    review_reasons: list[str]


class DuplicateResolution(BaseModel):
    issue_id: str
    kept_finding_id: str
    restored_finding_ids: list[str]
    reason: str
    evidence_message_ids: list[str]


class Feedback(BaseModel):
    issue_id: str | None = None
    item_ids: list[str] = Field(default_factory=list)
    advice: str
    rule_ids: list[str] = Field(default_factory=list)
    evidence_message_ids: list[str] = Field(default_factory=list)


class FinalAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1.0.0"
    week: Literal[4] = 4
    audit_id: str
    ticket_id: str
    status: Literal["completed", "blocked", "manual_review"]
    grade: str
    total_score: float | None = Field(default=None, ge=0, le=100)
    redline: dict | None = None
    preflight: dict | None = None
    dimensions: dict[str, DimensionResult] = Field(default_factory=dict)
    adjusted_raw_scores: dict[str, int] = Field(default_factory=dict)
    weighted_scores: dict[str, float] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    duplicate_resolutions: list[DuplicateResolution] = Field(default_factory=list)
    feedback: list[Feedback] = Field(default_factory=list)
    manual_review_reasons: list[str] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    technical_errors: list[dict] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)
    react_steps: list[dict] = Field(default_factory=list)
    scoring_version: str
    summary_version: str
    evaluation_mode: Literal["live", "offline_demo", "offline_test"] = "live"

    @model_validator(mode="after")
    def consistent_status(self):
        if self.status == "completed" and (self.total_score is None or self.manual_review_reasons):
            raise ValueError("A completed audit must have a valid score and no pending review")
        if self.status != "completed" and self.total_score is not None:
            raise ValueError("Blocked or review audits cannot publish a business total")
        return self
