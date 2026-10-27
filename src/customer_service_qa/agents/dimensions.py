"""Specialist assessment, strict score/evidence validation, and bounded retries."""

import json
import re
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from customer_service_qa.agents.dimension_prompts import build_dimension_prompt
from customer_service_qa.config import Settings, load_dimension_rubrics, load_scoring_config
from customer_service_qa.schemas.scoring import (
    DimensionAssessment,
    DimensionContext,
    DimensionName,
    DimensionResult,
    ItemResult,
)
from customer_service_qa.tools.professional_rules import get_professional_rules


class DimensionEvaluator(Protocol):
    def __call__(self, context: DimensionContext) -> DimensionAssessment | dict | str: ...


class LiveDimensionEvaluator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def __call__(self, context: DimensionContext) -> DimensionAssessment:
        if not self.settings.has_llm_api_key:
            raise RuntimeError("LLM_API_KEY is not configured")
        model = ChatOpenAI(
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key.get_secret_value(),
            base_url=self.settings.llm_base_url,
            temperature=0,
            timeout=self.settings.llm_timeout_seconds,
            max_retries=0,
            extra_body=self.settings.llm_extra_body or None,
        ).with_structured_output(DimensionAssessment, method="function_calling")
        return model.invoke(
            [
                SystemMessage(content=build_dimension_prompt(context.dimension)),
                HumanMessage(content=context.model_dump_json()),
            ]
        )


def build_dimension_context(
    dimension, conversation, preflight, rule_lookup=None
) -> DimensionContext:
    scoring = load_scoring_config()["dimensions"][dimension]
    rubric = load_dimension_rubrics()
    return DimensionContext(
        dimension=dimension,
        conversation=conversation,
        preflight=preflight,
        rubric={
            **scoring,
            "items": [
                {**item, "criterion": rubric["items"][item["id"]]} for item in scoring["items"]
            ],
            "shared_exemptions": rubric["shared_exemptions"],
            "version": rubric["version"],
        },
        professional_rules=(
            (rule_lookup or get_professional_rules)(conversation.parent_tag)
            if dimension == "professional_service"
            else None
        ),
    )


def parse_score(value: int | str, max_score: int) -> int:
    """Accept integers or a complete X/N expression; never salvage arbitrary text."""
    if type(value) is int:
        score = value
    elif isinstance(value, str):
        match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value)
        if not match or int(match[2]) != max_score:
            raise ValueError("Invalid score expression or denominator")
        score = int(match[1])
    else:
        raise ValueError("Score must be an integer or X/N")
    if not 0 <= score <= max_score:
        raise ValueError("Score out of range")
    return score


def _parse_assessment(value) -> DimensionAssessment:
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("```json\n") and value.endswith("```"):
            value = value[8:-3].strip()
        value = json.loads(value)
    return DimensionAssessment.model_validate(value)


def validate_assessment(value, context: DimensionContext) -> DimensionResult:
    assessment = _parse_assessment(value)
    if assessment.dimension != context.dimension:
        raise ValueError("Wrong assessment dimension")
    specs = {item["id"]: item for item in context.rubric["items"]}
    ids = [item.item_id for item in assessment.items]
    if len(ids) != len(specs) or set(ids) != set(specs):
        raise ValueError("Every scoring item must appear exactly once")
    messages = {m.message_id: m for m in context.conversation.messages}
    business = (
        {r.rule_id: r for r in context.professional_rules.rules}
        if context.professional_rules
        else {}
    )
    results = []
    for item in assessment.items:
        spec = specs[item.item_id]
        if not item.reason.strip():
            raise ValueError("Empty assessment reason")
        if not item.rule_ids or len(set(item.rule_ids)) != len(item.rule_ids):
            raise ValueError("Missing or duplicate rule references")
        for rule_id in item.rule_ids:
            if rule_id != item.item_id and (
                rule_id not in business or business[rule_id].item_id not in (None, item.item_id)
            ):
                raise ValueError("Unknown, cross-category or wrong-item rule")
        for evidence in item.evidence:
            if (
                evidence.message_id not in messages
                or not evidence.quote.strip()
                or evidence.quote not in messages[evidence.message_id].content
            ):
                raise ValueError("Evidence must quote an existing message verbatim")

        unavailable = (
            item.item_id == "CM-03" and not context.preflight.first_response_evaluable
        ) or (item.item_id == "CM-04" and not context.preflight.timing_available)
        if unavailable or item.status == "not_evaluable":
            if not unavailable and item.score is not None:
                raise ValueError("An unassessed item cannot have a score")
            score = None
            reason = "缺少有效时间戳或人工接入事件，无法评估。" if unavailable else item.reason
        else:
            score = parse_score(item.score, spec["max_score"])
            reason = item.reason
            if context.dimension != "professional_service" and score not in (0, 5):
                raise ValueError("Binary scoring item must be zero or full marks")
            if not item.evidence:
                raise ValueError("Scored items require dialogue evidence")
            if item.item_id == "PS-03" and score != 10:
                raise ValueError("PS-03 is full marks under the supplied rubric")
            if item.item_id in ("PS-01", "PS-02") and score < spec["max_score"]:
                rules = [business[r] for r in item.rule_ids if r in business]
                deductions = sum(rule.deduction for rule in rules)
                if item.item_id == "PS-02" and "PS-02" in item.rule_ids:
                    deductions += 5
                if not deductions or any(rule.item_id is None for rule in rules):
                    raise ValueError("Deduction needs applicable rules, without an exemption")
                if score != max(0, spec["max_score"] - deductions):
                    raise ValueError("Professional score disagrees with cited deductions")
            if item.item_id == "CM-03":
                expected = 0 if context.preflight.first_response_violation else 5
                if score != expected:
                    raise ValueError("First response score contradicts timestamps")
            if item.item_id == "CM-04" and not context.preflight.response_time_violations:
                if score != 5:
                    raise ValueError("No observed reply timeout: cannot deduct timing points")
        results.append(
            ItemResult(
                item_id=item.item_id,
                name=spec["name"],
                score=score,
                status="not_evaluable" if score is None else "scored",
                max_score=spec["max_score"],
                score_text="N/A" if score is None else f"{score}/{spec['max_score']}",
                deduction=None if score is None else spec["max_score"] - score,
                reason=reason,
                rule_ids=item.rule_ids,
                rule_texts=[
                    business[r].text if r in business else spec["criterion"] for r in item.rule_ids
                ],
                evidence=item.evidence,
            )
        )
    results.sort(key=lambda item: list(specs).index(item.item_id))
    partial = any(item.score is None for item in results)
    earned = sum(item.score for item in results if item.score is not None)
    available = sum(item.max_score for item in results if item.score is not None)
    maximum = context.rubric["raw_max_score"]
    return DimensionResult(
        dimension=context.dimension,
        status="partial" if partial else "completed",
        raw_score=None if partial else earned,
        max_score=maximum,
        score_text="N/A" if partial else f"{earned}/{maximum}",
        items=results,
        evaluated_score=earned,
        evaluated_max_score=available,
        review_reasons=[f"{item.item_id}: {item.reason}" for item in results if item.score is None],
    )


def failed_dimension(
    dimension: DimensionName, reason: str, *, errors=None, attempts=0, status="technical_error"
) -> DimensionResult:
    maximum = load_scoring_config()["dimensions"][dimension]["raw_max_score"]
    return DimensionResult(
        dimension=dimension,
        status=status,
        raw_score=None,
        max_score=maximum,
        score_text="N/A",
        fallback_score=0 if status == "technical_error" else None,
        review_reasons=[reason],
        errors=errors or [],
        attempts=attempts,
    )


def evaluate_dimension(
    context: DimensionContext, evaluator: DimensionEvaluator, max_attempts: int = 2
) -> DimensionResult:
    if not 1 <= max_attempts <= 3:
        raise ValueError("Attempts must be between one and three")
    errors = []
    for attempt in range(1, max_attempts + 1):
        try:
            result = validate_assessment(evaluator(context.model_copy(deep=True)), context)
            result.attempts = attempt
            result.errors = errors
            return result
        except Exception as error:
            # Provider/validation exceptions may contain the input or credentials.
            # Persist only type and a fixed message, never str(error).
            errors.append(
                {
                    "node": context.dimension,
                    "attempt": attempt,
                    "error_type": type(error).__name__,
                    "message": "维度模型调用或评分校验失败",
                }
            )
    return failed_dimension(
        context.dimension, "重试耗尽，请人工复核。", errors=errors, attempts=max_attempts
    )
