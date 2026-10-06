"""Regenerate synthetic week-three examples; run from the repository root."""

import json
from pathlib import Path

from customer_service_qa.config import Settings
from customer_service_qa.demo import demo_critical, demo_dimension, demo_payload
from customer_service_qa.graph import build_week3_graph
from customer_service_qa.reporting import render_markdown
from customer_service_qa.schemas.scoring import DIMENSIONS


def fail_dimension(_context):
    raise TimeoutError("Synthetic provider failure")


def blocked_critical(messages, preflight):
    result = demo_critical(messages, preflight)
    result.items[1].triggered = True
    result.items[1].evidence_message_ids = ["m003"]
    result.items[1].reason = "合成示例中的客服明确辱骂用户。"
    result.summary = "离线预设：CR-02命中，跳过三个维度。"
    return result


def main():
    folder = Path(__file__).resolve().parents[1] / "docs/week3/examples"
    folder.mkdir(parents=True, exist_ok=True)
    payload = demo_payload()
    (folder / "input.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for scenario in ("completed", "partial", "technical-error", "blocked"):
        payload = demo_payload()
        critical = demo_critical
        evaluators = dict.fromkeys(DIMENSIONS, demo_dimension)
        if scenario == "partial":
            for message in payload["messages"]:
                message.pop("timestamp")
        elif scenario == "technical-error":
            evaluators["professional_service"] = fail_dimension
        elif scenario == "blocked":
            payload["messages"][2]["content"] = "你真笨，不想帮你。"
            critical = blocked_critical
        audit = build_week3_graph(
            critical_evaluator=critical,
            dimension_evaluators=evaluators,
            settings=Settings(llm_model="offline-fixture"),
        ).invoke({"raw_input": payload})["final_audit"]
        audit["evaluation_mode"] = "offline_demo"
        (folder / f"{scenario}.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if scenario == "completed":
            (folder / "completed.md").write_text(render_markdown(audit), encoding="utf-8")


if __name__ == "__main__":
    main()
