"""Structured redline evaluation with deterministic validation and retry."""

import json
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from customer_service_qa.agents.prompts import CRITICAL_SYSTEM_PROMPT
from customer_service_qa.config import Settings
from customer_service_qa.schemas import (
    Message,
    PreflightReport,
    RedlineAssessment,
    RedlineResult,
)

EXPECTED_RULE_IDS = {"CR-01", "CR-02", "CR-03", "CR-04"}


class CriticalEvaluator(Protocol):
    def __call__(
        self, messages: list[Message], preflight: PreflightReport
    ) -> RedlineAssessment: ...


class LiveCriticalEvaluator:
    """Call an OpenAI-compatible chat model and request a Pydantic response."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def __call__(
        self, messages: list[Message], preflight: PreflightReport
    ) -> RedlineAssessment:
        if not self.settings.has_llm_api_key:
            raise RuntimeError("LLM_API_KEY is not configured")

        model = ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key.get_secret_value(),
            base_url=self.settings.llm_base_url,
            temperature=0,
            timeout=30,
            max_retries=0,
        )
        structured_model = model.with_structured_output(
            RedlineAssessment,
            method="function_calling",
        )
        payload = {
            "messages": [message.model_dump(mode="json") for message in messages],
            "preflight": preflight.model_dump(mode="json"),
        }
        result = structured_model.invoke(
            [
                SystemMessage(content=CRITICAL_SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]
        )
        return RedlineAssessment.model_validate(result)


def _validate_assessment(
    assessment: RedlineAssessment, messages: list[Message]
) -> RedlineResult:
    rule_ids = [item.rule_id for item in assessment.items]
    if len(rule_ids) != len(EXPECTED_RULE_IDS) or set(rule_ids) != EXPECTED_RULE_IDS:
        raise ValueError("The assessment must contain each redline rule exactly once")

    valid_message_ids = {message.message_id for message in messages}
    for item in assessment.items:
        unknown_ids = set(item.evidence_message_ids) - valid_message_ids
        if unknown_ids:
            raise ValueError(f"Unknown evidence message ids: {sorted(unknown_ids)}")
        if item.triggered and not item.evidence_message_ids:
            raise ValueError(f"Triggered rule {item.rule_id} must include evidence")

    triggered = any(item.triggered for item in assessment.items)
    return RedlineResult(
        items=assessment.items,
        triggered=triggered,
        gate_status="blocked" if triggered else "pass",
        summary=assessment.summary,
    )


def evaluate_redlines(
    messages: list[Message],
    preflight: PreflightReport,
    evaluator: CriticalEvaluator,
    max_attempts: int = 2,
) -> tuple[RedlineResult, list[dict]]:
    """Run and validate the semantic gate, returning review on technical failure."""

    if not preflight.input_valid:
        return (
            RedlineResult(
                items=[],
                triggered=False,
                gate_status="review",
                summary="输入未通过预检，需要人工复核。",
            ),
            [],
        )

    errors: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        try:
            assessment = evaluator(messages, preflight)
            if not isinstance(assessment, RedlineAssessment):
                assessment = RedlineAssessment.model_validate(assessment)
            return _validate_assessment(assessment, messages), errors
        except Exception as error:  # The graph must turn provider failures into review status.
            errors.append(
                {
                    "node": "critical_gate",
                    "attempt": attempt,
                    "error_type": type(error).__name__,
                    "message": str(error)[:240],
                }
            )

    return (
        RedlineResult(
            items=[],
            triggered=False,
            gate_status="review",
            summary="红线模型调用或结构校验失败，需要人工复核。",
        ),
        errors,
    )
