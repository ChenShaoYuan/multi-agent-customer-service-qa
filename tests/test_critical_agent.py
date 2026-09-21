from customer_service_qa.adapters import normalize_input
from customer_service_qa.agents import evaluate_redlines
from customer_service_qa.preflight import run_preflight
from customer_service_qa.schemas import RedlineAssessment, RedlineFinding


def _assessment(triggered_rule: str | None = None) -> RedlineAssessment:
    return RedlineAssessment(
        items=[
            RedlineFinding(
                rule_id=rule_id,
                triggered=rule_id == triggered_rule,
                reason="命中规则" if rule_id == triggered_rule else "未发现违规",
                evidence_message_ids=["m002"] if rule_id == triggered_rule else [],
            )
            for rule_id in ("CR-01", "CR-02", "CR-03", "CR-04")
        ],
        summary="测试结论",
    )


def _conversation():
    conversation = normalize_input(
        {
            "ticket_id": "T-6",
            "tag": "账户-登录异常",
            "parent_tag": "账户安全",
            "messages": [
                {"role": "end-user", "content": "无法登录"},
                {"role": "agent", "content": "您好，请提供报错信息"},
            ],
        }
    )
    return conversation, run_preflight(conversation)


def test_valid_assessment_derives_pass_status() -> None:
    conversation, preflight = _conversation()

    result, errors = evaluate_redlines(
        conversation.messages, preflight, lambda _messages, _preflight: _assessment()
    )

    assert result.gate_status == "pass"
    assert not result.triggered
    assert errors == []


def test_triggered_assessment_derives_blocked_status() -> None:
    conversation, preflight = _conversation()

    result, _ = evaluate_redlines(
        conversation.messages,
        preflight,
        lambda _messages, _preflight: _assessment("CR-02"),
    )

    assert result.gate_status == "blocked"
    assert result.triggered


def test_provider_failure_retries_then_returns_review() -> None:
    conversation, preflight = _conversation()
    attempts = 0

    def failing_evaluator(_messages, _preflight):
        nonlocal attempts
        attempts += 1
        raise TimeoutError("provider timeout")

    result, errors = evaluate_redlines(conversation.messages, preflight, failing_evaluator)

    assert result.gate_status == "review"
    assert attempts == 2
    assert len(errors) == 2


def test_unknown_evidence_id_returns_review() -> None:
    conversation, preflight = _conversation()
    invalid = _assessment("CR-01")
    invalid.items[0].evidence_message_ids = ["not-a-message"]

    result, errors = evaluate_redlines(
        conversation.messages, preflight, lambda _messages, _preflight: invalid
    )

    assert result.gate_status == "review"
    assert errors[0]["error_type"] == "ValueError"
