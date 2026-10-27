import copy

import pytest

from customer_service_qa.agents.summary_agent import DemoSummaryPlanner
from customer_service_qa.config import Settings
from customer_service_qa.demo import demo_critical, demo_dimension, demo_payload
from customer_service_qa.graph import build_week3_graph, build_week4_graph
from customer_service_qa.schemas.audit import FinalAudit, FinalizeArguments
from customer_service_qa.schemas.scoring import DIMENSIONS
from customer_service_qa.summary import apply_summary, calculate_total, grade_score, prepare_audit


def graph4(**kwargs):
    return build_week4_graph(
        critical_evaluator=kwargs.pop("critical_evaluator", demo_critical),
        dimension_evaluators=kwargs.pop(
            "dimension_evaluators", dict.fromkeys(DIMENSIONS, demo_dimension)
        ),
        summary_planner=kwargs.pop("summary_planner", DemoSummaryPlanner()),
        settings=kwargs.pop("settings", Settings(_env_file=None, llm_model="offline-fixture")),
        **kwargs,
    )


def state3():
    return build_week3_graph(
        critical_evaluator=demo_critical,
        dimension_evaluators=dict.fromkeys(DIMENSIONS, demo_dimension),
    ).invoke({"raw_input": demo_payload()})


@pytest.mark.parametrize(
    "score,grade",
    [
        (0, "严重问题"),
        (59.99, "严重问题"),
        (60, "合格"),
        (89.99, "合格"),
        (90, "优秀"),
        (100, "优秀"),
    ],
)
def test_grade_boundaries(score, grade):
    assert grade_score(score) == grade


@pytest.mark.parametrize("score", [-1, 101, float("nan"), float("inf")])
def test_invalid_grade_scores(score):
    with pytest.raises(ValueError):
        grade_score(score)


def test_exact_weights_and_real_full_workflow():
    audit = graph4().invoke({"raw_input": demo_payload()})["final_audit"]
    FinalAudit.model_validate(audit)
    assert audit["total_score"] == 96 and audit["grade"] == "优秀"
    assert audit["weighted_scores"] == {
        "service_process": 16,
        "professional_service": 40,
        "communication": 40,
    }
    assert [s["action"] for s in audit["react_steps"]] == ["inspect_audit", "finalize_audit"]
    assert len(audit["trace"]) == 7
    assert audit["trace"][-1]["node"] == "summary_agent"
    assert audit["feedback"][0]["item_ids"] == ["SP-01"]


@pytest.mark.parametrize(
    "scores",
    [
        {},
        {"service_process": 25, "professional_service": None, "communication": 25},
        {"service_process": True, "professional_service": 50, "communication": 25},
    ],
)
def test_totals_never_impute_invalid_scores(scores):
    with pytest.raises(ValueError):
        calculate_total(scores)


def duplicate_state():
    state = state3()
    for name, item_id, score in (
        ("service_process", "SP-03", 0),
        ("professional_service", "PS-01", 20),
    ):
        result = state[f"{name}_result"]
        item = next(i for i in result["items"] if i["item_id"] == item_id)
        item.update(
            score=score,
            deduction=item["max_score"] - score,
            score_text=f"{score}/{item['max_score']}",
            reason="未向用户提供密码重置步骤。",
            evidence=[{"message_id": "m003", "quote": "您好"}],
        )
        result["raw_score"] = sum(i["score"] for i in result["items"])
    return state


def duplicate_args():
    return {
        "duplicate_groups": [
            {
                "finding_ids": ["service_process:SP-03", "professional_service:PS-01"],
                "reason": "两个维度均针对同一次回复未提供密码重置步骤扣分。",
                "evidence_message_ids": ["m003"],
            }
        ],
        "review_reasons": [],
    }


def test_dedup_preserves_original_results_and_keeps_largest_weighted_loss():
    prepared = prepare_audit(duplicate_state())
    before = prepared.model_dump()
    result = apply_summary(prepared, FinalizeArguments.model_validate(duplicate_args()))
    assert prepared.model_dump() == before
    assert result.total_score == 88  # greeting -4 and professional -8, SP-03 -4 restored.
    assert result.grade == "合格"
    assert result.dimensions["service_process"].raw_score == 15
    assert result.adjusted_raw_scores["service_process"] == 20
    assert result.duplicate_resolutions[0].kept_finding_id == "professional_service:PS-01"
    duplicates = [f for f in result.findings if f.item_id in ("SP-03", "PS-01")]
    assert len({f.issue_id for f in duplicates}) == 1


@pytest.mark.parametrize(
    "fault",
    ["unknown", "repeated", "same_dimension", "wrong_evidence", "unrelated", "multi_clause"],
)
def test_unsafe_dedup_is_rejected(fault):
    state, args = duplicate_state(), duplicate_args()
    group = args["duplicate_groups"][0]
    if fault == "unknown":
        group["finding_ids"][0] = "missing"
    elif fault == "repeated":
        args["duplicate_groups"].append(copy.deepcopy(group))
    elif fault == "same_dimension":
        group["finding_ids"] = ["service_process:SP-01", "service_process:SP-03"]
    elif fault == "wrong_evidence":
        group["evidence_message_ids"] = ["m999"]
    elif fault == "unrelated":
        group["finding_ids"][0] = "service_process:SP-01"
    else:
        state["professional_service_result"]["items"][0]["rule_ids"].append("another-clause")
    with pytest.raises(ValueError):
        apply_summary(prepare_audit(state), FinalizeArguments.model_validate(args))


@pytest.mark.parametrize("missing", ["preflight_report", "redline_result", "communication_result"])
def test_missing_upstream_contract_stays_review(missing):
    state = state3()
    state.pop(missing)
    result = prepare_audit(state)
    assert result.status == "manual_review" and result.manual_review_reasons
    assert result.total_score is None and result.alerts


def test_partial_and_failed_branches_never_receive_total():
    payload = demo_payload()
    for message in payload["messages"]:
        message.pop("timestamp")
    audit = graph4().invoke({"raw_input": payload})["final_audit"]
    assert audit["total_score"] is None and audit["status"] == "manual_review"
    assert audit["dimensions"]["service_process"]["raw_score"] == 20
    assert not audit["react_steps"]


def test_invalid_payload_and_redline_share_the_final_contract():
    for payload in ({}, [], None):
        result = graph4().invoke({"raw_input": payload})["final_audit"]
        assert FinalAudit.model_validate(result).status == "manual_review"

    def blocked(messages, report):
        result = demo_critical(messages, report)
        result.items[1].triggered = True
        result.items[1].evidence_message_ids = ["m003"]
        return result

    result = graph4(critical_evaluator=blocked).invoke({"raw_input": demo_payload()})["final_audit"]
    assert FinalAudit.model_validate(result).status == "blocked"
    assert result["grade"] == "严重不合格" and result["total_score"] is None
    assert result["dimensions"] == {} and not result["react_steps"]


def test_rule_tool_failure_preserves_other_dimensions():
    def failed(_):
        raise TimeoutError("private provider response")

    result = graph4(rule_lookup=failed).invoke({"raw_input": demo_payload()})["final_audit"]
    assert result["status"] == "manual_review" and result["total_score"] is None
    assert result["dimensions"]["communication"]["raw_score"] == 25
    assert result["dimensions"]["professional_service"]["fallback_score"] == 0
