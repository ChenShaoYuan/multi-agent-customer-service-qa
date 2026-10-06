from threading import Barrier

import pytest

from customer_service_qa.config import Settings
from customer_service_qa.demo import demo_critical, demo_dimension, demo_payload
from customer_service_qa.graph import build_week3_graph
from customer_service_qa.schemas.scoring import DIMENSIONS


def graph(evaluators=None, critical=demo_critical):
    return build_week3_graph(
        critical_evaluator=critical,
        dimension_evaluators={name: demo_dimension for name in DIMENSIONS} | (evaluators or {}),
        settings=Settings(_env_file=None, llm_model="offline-fixture"),
    )


def test_three_nodes_run_concurrently_and_join_exactly_once():
    barrier = Barrier(3, timeout=10)

    def simultaneous(context):
        barrier.wait()  # Sequential implementation breaks the barrier instead of passing.
        return demo_dimension(context)

    result = graph({name: simultaneous for name in DIMENSIONS}).invoke(
        {"raw_input": demo_payload()}
    )
    audit = result["final_audit"]
    assert audit["status"] == "dimensions_completed" and audit["total_score"] is None
    assert [audit["dimensions"][name]["raw_score"] for name in DIMENSIONS] == [20, 50, 25]
    names = [trace["node"] for trace in result["node_traces"]]
    assert len(names) == 7 and names.count("collect_dimensions") == 1
    assert set(names[3:6]) == set(DIMENSIONS)
    assert names[-1] == "collect_dimensions"


def test_one_failed_branch_keeps_two_successes_and_all_traces():
    def failed(_):
        raise TimeoutError("private data")

    result = graph({"professional_service": failed}).invoke({"raw_input": demo_payload()})
    audit = result["final_audit"]
    assert audit["status"] == "manual_review" and not audit["ready_for_summary"]
    assert audit["dimensions"]["service_process"]["raw_score"] == 20
    assert audit["dimensions"]["communication"]["raw_score"] == 25
    failed_result = audit["dimensions"]["professional_service"]
    assert failed_result["raw_score"] is None and failed_result["fallback_score"] == 0
    assert len(audit["technical_errors"]) == 2 and len(audit["trace"]) == 7


@pytest.mark.parametrize("mode", ["blocked", "invalid", "critical_error"])
def test_gate_short_circuits_all_dimension_agents(mode):
    calls = []

    def forbidden(_):
        calls.append(1)
        raise AssertionError("Dimension must not run")

    def critical(messages, report):
        if mode == "critical_error":
            raise TimeoutError("private credential")
        assessment = demo_critical(messages, report)
        if mode == "blocked":
            assessment.items[0].triggered = True
            assessment.items[0].evidence_message_ids = ["m003"]
        return assessment

    result = graph({name: forbidden for name in DIMENSIONS}, critical).invoke(
        {"raw_input": {} if mode == "invalid" else demo_payload()}
    )
    assert not calls and "dimensions" not in result["final_audit"]
    assert result["final_audit"]["status"] == ("blocked" if mode == "blocked" else "manual_review")


def test_unknown_category_reviews_professional_without_model_call():
    payload = demo_payload()
    payload["parent_tag"] = "未收录类别"
    calls = []

    def forbidden(_):
        calls.append(1)
        raise AssertionError("Unknown category must not call model")

    audit = graph({"professional_service": forbidden}).invoke({"raw_input": payload})["final_audit"]
    assert not calls
    professional = audit["dimensions"]["professional_service"]
    assert professional["status"] == "manual_review" and professional["attempts"] == 0
    assert professional["tool_trace"][0]["status"] == "not_found"
    assert audit["dimensions"]["service_process"]["raw_score"] == 20


def test_missing_timing_routes_partial_result_to_review():
    payload = demo_payload()
    for message in payload["messages"]:
        message.pop("timestamp")
    audit = graph().invoke({"raw_input": payload})["final_audit"]
    assert audit["status"] == "manual_review"
    assert audit["dimensions"]["communication"]["status"] == "partial"
    assert len(audit["manual_review_reasons"]) == 2


def test_successful_gate_retry_is_counted():
    calls = []

    def flaky(messages, report):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("first attempt")
        return demo_critical(messages, report)

    result = graph(critical=flaky).invoke({"raw_input": demo_payload()})
    assert result["node_traces"][2]["retry_count"] == 1
