import json

import pytest

from customer_service_qa.adapters import normalize_input
from customer_service_qa.cli import main
from customer_service_qa.demo import demo_payload
from customer_service_qa.preflight import run_preflight


@pytest.mark.parametrize("fault", ["backwards", "mixed_timezone", "unanswered"])
def test_bad_timing_is_not_reported_as_a_compliant_reply(fault):
    payload = demo_payload()
    if fault == "backwards":
        payload["messages"][2]["timestamp"] = "2026-09-27T09:59:00+08:00"
    elif fault == "mixed_timezone":
        payload["messages"][2]["timestamp"] = "2026-09-27T10:00:30"
    else:
        payload["messages"].pop()
    report = run_preflight(normalize_input(payload))
    assert not report.timing_available and report.timing_errors
    if fault != "unanswered":
        assert not report.first_response_evaluable


@pytest.mark.parametrize("fault", ["duplicate_id", "blank_id", "null_content", "list_content"])
def test_bad_message_identity_or_content_is_rejected(fault):
    payload = demo_payload()
    message = payload["messages"][2]
    if fault == "duplicate_id":
        message["message_id"] = "m002"
    elif fault == "blank_id":
        message["message_id"] = " "
    else:
        message["content"] = None if fault == "null_content" else ["text"]
    assert not run_preflight(normalize_input(payload)).input_valid


def test_cli_demo_writes_json_and_readable_markdown(monkeypatch, tmp_path):
    for format_, suffix in (("json", ".json"), ("markdown", ".md")):
        path = tmp_path / ("report" + suffix)
        monkeypatch.setattr(
            "sys.argv", ["qa", "--demo", "--format", format_, "--output", str(path)]
        )
        assert main() == 0
        content = path.read_text("utf-8")
        if format_ == "json":
            report = json.loads(content)
            assert report["evaluation_mode"] == "offline_demo"
            assert report["dimensions"]["service_process"]["score_text"] == "20/25"
        else:
            assert "SP-01" in content and "m003" in content
            assert "仅用于演示和工程测试" in content


def test_missing_key_returns_review_without_a_network_request():
    from test_dimension_scoring import context_for

    from customer_service_qa.agents.dimensions import LiveDimensionEvaluator, evaluate_dimension
    from customer_service_qa.config import Settings

    result = evaluate_dimension(
        context_for(), LiveDimensionEvaluator(Settings(_env_file=None, llm_api_key=None))
    )
    assert result.status == "technical_error" and result.raw_score is None
