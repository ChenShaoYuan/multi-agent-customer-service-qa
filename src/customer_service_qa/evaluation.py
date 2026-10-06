"""Resumable real-data evaluation; report engineering validity separately from label quality."""

import argparse
import hashlib
import json
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter

from customer_service_qa.agents.summary_agent import DemoSummaryPlanner
from customer_service_qa.config import PROJECT_ROOT, Settings
from customer_service_qa.demo import demo_critical, demo_dimension
from customer_service_qa.graph import build_week4_graph
from customer_service_qa.schemas.audit import FinalAudit
from customer_service_qa.schemas.scoring import DIMENSIONS
from customer_service_qa.summary import prepare_audit


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def run_fingerprint(settings: Settings, mode: str) -> str:
    # No credentials in metadata, checkpoints, or fingerprints.
    config = settings.model_dump(mode="json", exclude={"llm_api_key"})
    files = {}
    for folder in ("src", "configs", "data/raw"):
        for path in sorted((PROJECT_ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".yaml", ".json"):
                files[path.relative_to(PROJECT_ROOT).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return digest({"mode": mode, "settings": config, "files": files})


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    temporary.replace(path)


def metrics(records: list[dict], expected: dict | None = None) -> dict:
    count = len(records)
    valid = 0
    statuses, dimensions, alerts = Counter(), Counter(), Counter()
    latencies, technical = [], 0
    for record in records:
        audit = record["result"]
        try:
            FinalAudit.model_validate(audit)
            valid += 1
        except ValueError:
            pass
        statuses[audit["status"]] += 1
        latencies.append(record["duration_seconds"])
        technical += bool(audit["technical_errors"])
        for name, result in audit["dimensions"].items():
            dimensions[f"{name}:{result['status']}"] += 1
        alerts.update(a["code"] for a in audit["alerts"])
    ordered = sorted(latencies)
    report = {
        "record_count": count,
        "final_schema_valid_count": valid,
        "final_schema_valid_rate": valid / count if count else None,
        "status_counts": dict(statuses),
        "dimension_status_counts": dict(dimensions),
        "records_with_technical_errors": technical,
        "alert_counts": dict(alerts),
        "latency_seconds": {
            "mean": round(mean(latencies), 3) if count else None,
            "p50": ordered[math.ceil(count * 0.5) - 1] if count else None,
            "p95": ordered[math.ceil(count * 0.95) - 1] if count else None,
        },
        "business_accuracy": None,
        "accuracy_note": "无人工金标时不能报告业务准确率。运行契约通过率含受控复核结果。",
    }
    if expected:
        comparison = []
        tp = fp = fn = gate_ok = grade_ok = 0
        errors = []
        for record in records:
            truth = expected.get(str(record["index"]))
            if truth is None:
                continue
            actual = record["result"]
            predicted_gate = (actual.get("redline") or {}).get("gate_status", "review")
            expected_gate = truth["gate_status"]
            gate_ok += predicted_gate == expected_gate
            grade_ok += actual["grade"] == truth["grade"]
            tp += predicted_gate == "blocked" and expected_gate == "blocked"
            fp += predicted_gate == "blocked" and expected_gate != "blocked"
            fn += predicted_gate != "blocked" and expected_gate == "blocked"
            score_error = None
            if truth.get("total_score") is not None and actual["total_score"] is not None:
                score_error = abs(truth["total_score"] - actual["total_score"])
                errors.append(score_error)
            comparison.append(
                {
                    "index": record["index"],
                    "expected": truth,
                    "actual_gate": predicted_gate,
                    "actual_grade": actual["grade"],
                    "actual_score": actual["total_score"],
                    "score_absolute_error": score_error,
                    "review_reasons": actual["manual_review_reasons"],
                }
            )
        n = len(comparison)
        report["reference_comparison"] = {
            "label_status": "rule_authored_not_human_reviewed",
            "count": n,
            "gate_agreement": gate_ok / n if n else None,
            "grade_agreement": grade_ok / n if n else None,
            "redline_precision": tp / (tp + fp) if tp + fp else None,
            "redline_recall": tp / (tp + fn) if tp + fn else None,
            "score_mae_on_scorable_pairs": mean(errors) if errors else None,
            "scorable_pair_count": len(errors),
            "cases": comparison,
        }
    return report


def run_batch(
    payloads,
    runner,
    output_dir: Path,
    fingerprint: str,
    *,
    mode="live",
    workers=2,
    resume=False,
    expected=None,
) -> dict:
    if not 1 <= workers <= 4:
        raise ValueError("Workers must be between 1 and 4")
    started = perf_counter()
    record_dir = output_dir / "records"
    record_dir.mkdir(parents=True, exist_ok=True)
    records, pending = [], []
    for index, payload in enumerate(payloads):
        path = record_dir / f"{index:04d}.json"
        input_hash = digest(payload)
        if path.exists():
            if not resume:
                raise ValueError("Output already exists; use --resume or choose a new directory")
            old = json.loads(path.read_text("utf-8"))
            if old["input_sha256"] != input_hash or old["run_fingerprint"] != fingerprint:
                raise ValueError("Cannot resume records from changed code, config or input")
            FinalAudit.model_validate(old["result"])
            records.append(old)
        else:
            pending.append((index, payload, input_hash, path))

    def evaluate(job):
        index, payload, input_hash, path = job
        began = perf_counter()
        try:
            output = runner(payload)
            result = FinalAudit.model_validate(output).model_dump(mode="json")
        except Exception as error:
            result = prepare_audit(
                {
                    "technical_errors": [
                        {
                            "node": "batch_runner",
                            "attempt": 1,
                            "error_type": type(error).__name__,
                            "message": "批量单条执行异常",
                        }
                    ]
                }
            ).model_dump(mode="json")
        result["evaluation_mode"] = mode
        record = {
            "index": index,
            "input_sha256": input_hash,
            "run_fingerprint": fingerprint,
            "duration_seconds": round(perf_counter() - began, 3),
            "result": result,
        }
        atomic_json(path, record)
        return record

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate, job) for job in pending]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(
                json.dumps(
                    {
                        "completed": len(records),
                        "total": len(payloads),
                        "index": record["index"],
                        "status": record["result"]["status"],
                    }
                ),
                flush=True,
            )
    records.sort(key=lambda row: row["index"])
    report = metrics(records, expected)
    report.update(
        run_fingerprint=fingerprint,
        evaluation_mode=mode,
        workers=workers,
        records_resumed=len(records) - len(pending),
        records_executed=len(pending),
        execution_wall_seconds=round(perf_counter() - started, 3),
        generated_at=datetime.now(UTC).isoformat(),
    )
    atomic_json(output_dir / "metrics.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate historical or reference conversations")
    parser.add_argument(
        "--dataset", type=Path, default=PROJECT_ROOT / "data/raw/sample-conversations.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--demo", action="store_true", help="Offline fixture runner, not model evaluation"
    )
    parser.add_argument("--rules-transport", choices=["local", "mcp"], default="local")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text("utf-8"))
    reference = isinstance(dataset, dict) and "cases" in dataset
    rows = dataset["cases"] if reference else dataset
    if not isinstance(rows, list) or not rows:
        parser.error("Dataset must contain a nonempty list")
    if args.limit is not None:
        if args.limit < 1:
            parser.error("Limit must be positive")
        rows = rows[: args.limit]
    payloads = [row["payload"] for row in rows] if reference else rows
    expected = {str(i): row["expected"] for i, row in enumerate(rows)} if reference else None
    settings = Settings(rules_transport=args.rules_transport, prompt_version="0.3.0")
    if args.demo:
        graph = build_week4_graph(
            critical_evaluator=demo_critical,
            dimension_evaluators=dict.fromkeys(DIMENSIONS, demo_dimension),
            summary_planner=DemoSummaryPlanner(),
            settings=settings,
        )
    else:
        graph = build_week4_graph(settings=settings)
    mode = "offline_test" if args.demo else "live"
    run_batch(
        payloads,
        lambda payload: graph.invoke({"raw_input": payload})["final_audit"],
        args.output,
        run_fingerprint(settings, mode),
        mode=mode,
        workers=args.workers,
        resume=args.resume,
        expected=expected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
