import json

import pytest

from customer_service_qa.adapters import normalize_input
from customer_service_qa.agents.dimensions import (
    build_dimension_context,
    evaluate_dimension,
    parse_score,
    validate_assessment,
)
from customer_service_qa.demo import demo_dimension, demo_payload
from customer_service_qa.preflight import run_preflight


def context_for(dimension="service_process", payload=None):
    conversation = normalize_input(payload or demo_payload())
    return build_dimension_context(dimension, conversation, run_preflight(conversation))


@pytest.mark.parametrize(
    "value,maximum,expected", [(0, 5, 0), (" 5 / 5 ", 5, 5), ("20/30", 30, 20)]
)
def test_score_formats(value, maximum, expected):
    assert parse_score(value, maximum) == expected


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        5.0,
        None,
        "5",
        "score: 5/5",
        "5/5 extra",
        "-1/5",
        "6/5",
        "5/10",
        "3.5/5",
        "__import__('os')",
    ],
)
def test_invalid_scores_are_rejected(value):
    with pytest.raises(ValueError):
        parse_score(value, 5)


@pytest.mark.parametrize("encoding", ["dict", "json", "fenced"])
def test_scores_are_calculated_from_validated_items(encoding):
    context = context_for()
    value = demo_dimension(context)
    if encoding != "dict":
        value = json.dumps(value, ensure_ascii=False)
        if encoding == "fenced":
            value = "```json\n" + value + "\n```"
    result = validate_assessment(value, context)
    assert result.raw_score == 20
    assert result.score_text == "20/25"
    assert result.items[0].deduction == 5
    assert result.items[0].rule_texts[0] == context.rubric["items"][0]["criterion"]


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_dimension",
        "missing_item",
        "duplicate_item",
        "wrong_rule",
        "duplicate_rule",
        "fake_quote",
        "fake_message",
        "no_evidence",
        "partial_points",
        "unknown_field",
        "empty_reason",
        "unassessed_with_score",
    ],
)
def test_invalid_model_contracts(fault):
    context = context_for()
    value = demo_dimension(context)
    item = value["items"][0]
    if fault == "wrong_dimension":
        value["dimension"] = "communication"
    elif fault == "missing_item":
        value["items"].pop()
    elif fault == "duplicate_item":
        value["items"][1] = item.copy()
    elif fault == "wrong_rule":
        item["rule_ids"] = ["SP-99"]
    elif fault == "duplicate_rule":
        item["rule_ids"] *= 2
    elif fault == "fake_quote":
        item["evidence"][0]["quote"] = "模型虚构的原文"
    elif fault == "fake_message":
        item["evidence"][0]["message_id"] = "missing"
    elif fault == "no_evidence":
        item["evidence"] = []
    elif fault == "partial_points":
        item["score"] = "3/5"
    elif fault == "unknown_field":
        value["total_score"] = 100
    elif fault == "empty_reason":
        item["reason"] = " "
    else:
        item["status"] = "not_evaluable"
    with pytest.raises(ValueError):
        validate_assessment(value, context)


def test_missing_timestamps_force_partial_without_renormalization():
    payload = demo_payload()
    for message in payload["messages"]:
        message.pop("timestamp")
    context = context_for("communication", payload)
    result = validate_assessment(demo_dimension(context), context)
    assert result.status == "partial"
    assert result.raw_score is None and result.fallback_score is None
    assert (result.evaluated_score, result.evaluated_max_score) == (15, 15)
    assert [item.score for item in result.items] == [5, 5, None, None, 5]


def test_professional_deduction_is_bound_to_actual_category_rule():
    context = context_for("professional_service")
    value = demo_dimension(context)
    rule = next(rule for rule in context.professional_rules.rules if rule.item_id == "PS-01")
    value["items"][0]["score"] = f"{30 - rule.deduction}/30"
    value["items"][0]["rule_ids"] = [rule.rule_id]
    result = validate_assessment(value, context)
    assert result.raw_score == 50 - rule.deduction
    assert result.items[0].rule_texts == [rule.text]
    value["items"][0]["score"] = "15/30"
    with pytest.raises(ValueError, match="disagrees"):
        validate_assessment(value, context)


@pytest.mark.parametrize("fault", ["other_category", "wrong_item", "exemption", "ps03"])
def test_professional_invalid_deductions(fault):
    from customer_service_qa.tools.professional_rules import get_professional_rules

    context = context_for("professional_service")
    value = demo_dimension(context)
    item = value["items"][0]
    item["score"] = "20/30"
    if fault == "other_category":
        item["rule_ids"] = [get_professional_rules("订单管理").rules[0].rule_id]
    elif fault == "wrong_item":
        item["rule_ids"] = [
            next(r.rule_id for r in context.professional_rules.rules if r.item_id == "PS-02")
        ]
    elif fault == "exemption":
        item["rule_ids"] = [
            next(r.rule_id for r in context.professional_rules.rules if r.item_id is None)
        ]
    else:
        item["score"] = "30/30"
        value["items"][2]["score"] = "5/10"
    with pytest.raises(ValueError):
        validate_assessment(value, context)


def test_retry_success_and_failure_are_distinct_from_business_zero():
    context = context_for()
    calls = []

    def flaky(ctx):
        calls.append(1)
        if len(calls) == 1:
            return "not json"
        return demo_dimension(ctx)

    result = evaluate_dimension(context, flaky)
    assert result.status == "completed" and result.attempts == 2
    assert len(result.errors) == 1 and result.raw_score == 20

    def failed(_):
        raise RuntimeError("private dialogue and SECRET_TOKEN must not be logged")

    result = evaluate_dimension(context, failed)
    assert result.status == "technical_error" and result.attempts == 2
    assert result.raw_score is None and result.fallback_score == 0
    assert "SECRET_TOKEN" not in result.model_dump_json()


def test_timing_cannot_contradict_preflight():
    context = context_for("communication")
    for index in (2, 3):
        value = demo_dimension(context)
        value["items"][index]["score"] = "0/5"
        with pytest.raises(ValueError):
            validate_assessment(value, context)


@pytest.mark.parametrize(
    "dimension,index,field",
    [
        ("professional_service", 1, "rule_ids"),
        ("professional_service", 2, "rule_ids"),
        ("communication", 4, "evidence"),
    ],
)
def test_full_marks_still_require_rules_and_evidence(dimension, index, field):
    context = context_for(dimension)
    value = demo_dimension(context)
    value["items"][index][field] = []
    with pytest.raises(ValueError):
        validate_assessment(value, context)
