import json

import pytest
from test_week4_summary import graph4

from customer_service_qa.demo import demo_payload
from customer_service_qa.evaluation import metrics, run_batch


def test_batch_checkpoints_resume_without_repeating_model_calls(tmp_path):
    calls = []
    graph = graph4()

    def run(payload):
        calls.append(1)
        return graph.invoke({"raw_input": payload})["final_audit"]

    payloads = [demo_payload(), {}]
    report = run_batch(payloads, run, tmp_path, "revision-a", mode="offline_test", workers=2)
    assert len(calls) == 2 and report["final_schema_valid_rate"] == 1
    assert report["status_counts"] == {"completed": 1, "manual_review": 1}
    resumed = run_batch(payloads, run, tmp_path, "revision-a", mode="offline_test", resume=True)
    assert len(calls) == 2 and resumed["records_resumed"] == 2
    with pytest.raises(ValueError, match="changed"):
        run_batch(payloads, run, tmp_path, "revision-b", resume=True)
    assert json.loads((tmp_path / "metrics.json").read_text("utf-8"))["business_accuracy"] is None


def test_reference_metrics_name_the_non_gold_label_source():
    result = graph4().invoke({"raw_input": demo_payload()})["final_audit"]
    result["evaluation_mode"] = "offline_test"
    records = [{"index": 0, "duration_seconds": 1, "result": result}]
    report = metrics(records, {"0": {"gate_status": "pass", "grade": "优秀", "total_score": 100}})
    reference = report["reference_comparison"]
    assert reference["gate_agreement"] == 1 and reference["score_mae_on_scorable_pairs"] == 4
    assert reference["redline_precision"] is None
    assert reference["label_status"] == "rule_authored_not_human_reviewed"
    assert report["business_accuracy"] is None


def test_batch_worker_crash_does_not_abort_other_records(tmp_path):
    graph = graph4()

    def runner(payload):
        if payload.get("crash"):
            raise TimeoutError("private data")
        return graph.invoke({"raw_input": payload})["final_audit"]

    report = run_batch(
        [demo_payload(), {"crash": True}], runner, tmp_path, "a", mode="offline_test"
    )
    assert report["record_count"] == 2 and report["records_with_technical_errors"] == 1
    assert "private data" not in (tmp_path / "records/0001.json").read_text("utf-8")
