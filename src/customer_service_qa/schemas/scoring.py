"""Contracts separating model assessments from validated business scores."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from customer_service_qa.schemas.models import NormalizedConversation, PreflightReport

DimensionName = Literal["service_process", "professional_service", "communication"]
DIMENSIONS: tuple[DimensionName, ...] = (
    "service_process",
    "professional_service",
    "communication",
)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    quote: str = Field(min_length=1)


class ItemAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    status: Literal["scored", "not_evaluable"] = "scored"
    score: StrictInt | StrictStr | None
    reason: str = Field(min_length=1)
    rule_ids: list[str] = Field(
        min_length=1, description="必须非空。满分或默认给分也引用当前item_id；扣分引用适用规则ID。"
    )
    evidence: list[Evidence] = Field(
        description="scored项至少一条真实原文证据；无转接等未发现违规的项引用审核上下文消息。"
    )


class DimensionAssessment(BaseModel):
    """LLM output; totals are deliberately absent and calculated in Python."""

    model_config = ConfigDict(extra="forbid")
    dimension: DimensionName
    items: list[ItemAssessment]


class BusinessRule(BaseModel):
    rule_id: str
    item_id: str | None  # None denotes an exemption applying to the category.
    text: str
    deduction: int = 0


class RuleBundle(BaseModel):
    parent_tag: str
    source: str
    version: str
    rules: list[BusinessRule]


class DimensionContext(BaseModel):
    dimension: DimensionName
    conversation: NormalizedConversation
    preflight: PreflightReport
    rubric: dict
    professional_rules: RuleBundle | None = None


class ItemResult(BaseModel):
    item_id: str
    name: str
    status: Literal["scored", "not_evaluable"]
    score: int | None
    max_score: int
    score_text: str
    deduction: int | None
    reason: str
    rule_ids: list[str]
    rule_texts: list[str]
    evidence: list[Evidence]


class DimensionResult(BaseModel):
    dimension: DimensionName
    status: Literal["completed", "partial", "technical_error", "manual_review"]
    raw_score: int | None
    max_score: int
    score_text: str
    evaluated_score: int = 0
    evaluated_max_score: int = 0
    fallback_score: int | None = None  # Technical placeholder, never a business deduction.
    items: list[ItemResult] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    attempts: int = 0
    tool_trace: list[dict] = Field(default_factory=list)
