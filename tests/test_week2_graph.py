from customer_service_qa.graph import build_week2_graph
from customer_service_qa.schemas import RedlineAssessment, RedlineFinding


def _payload() -> dict:
    return {
        "ticket_id": "T-7",
        "tag": "账户-登录异常",
        "parent_tag": "账户安全",
        "messages": [
            {"role": "end-user", "content": "无法登录"},
            {"role": "agent", "content": "您好，请提供报错信息"},
        ],
    }


def _evaluator(triggered_rule: str | None = None):
    def evaluate(_messages, _preflight):
        return RedlineAssessment(
            items=[
                RedlineFinding(
                    rule_id=rule_id,
                    triggered=rule_id == triggered_rule,
                    reason="测试",
                    evidence_message_ids=["m002"] if rule_id == triggered_rule else [],
                )
                for rule_id in ("CR-01", "CR-02", "CR-03", "CR-04")
            ],
            summary="测试",
        )

    return evaluate


def test_pass_route_is_ready_for_week_three() -> None:
    result = build_week2_graph(evaluator=_evaluator()).invoke({"raw_input": _payload()})

    assert result["gate_status"] == "pass"
    assert result["final_audit"]["status"] == "ready_for_dimension_audit"
    assert result["final_audit"]["ready_for_dimension_audit"] is True
    assert len(result["node_traces"]) == 4


def test_blocked_route_short_circuits_dimension_audit() -> None:
    result = build_week2_graph(evaluator=_evaluator("CR-02")).invoke(
        {"raw_input": _payload()}
    )

    assert result["gate_status"] == "blocked"
    assert result["final_audit"]["status"] == "blocked"
    assert result["final_audit"]["grade"] == "严重不合格"


def test_invalid_input_routes_to_manual_review_without_calling_evaluator() -> None:
    called = False

    def should_not_run(_messages, _preflight):
        nonlocal called
        called = True
        return _evaluator()(_messages, _preflight)

    result = build_week2_graph(evaluator=should_not_run).invoke({"raw_input": {}})

    assert result["gate_status"] == "review"
    assert result["final_audit"]["status"] == "manual_review"
    assert called is False
