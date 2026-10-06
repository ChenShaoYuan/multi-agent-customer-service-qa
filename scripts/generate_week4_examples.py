"""Reproduce offline Week 4 paths; these fixtures are not model accuracy evidence."""

import json
from pathlib import Path

from customer_service_qa.agents.summary_agent import DemoSummaryPlanner
from customer_service_qa.config import PROJECT_ROOT, Settings
from customer_service_qa.demo import demo_critical, demo_dimension, demo_payload
from customer_service_qa.graph import build_week4_graph
from customer_service_qa.reporting import render_markdown
from customer_service_qa.schemas.scoring import DIMENSIONS


def blocked(messages, report):
    answer = demo_critical(messages, report)
    answer.items[1].triggered = True
    answer.items[1].evidence_message_ids = ["m003"]
    return answer


def failed(_context):
    raise TimeoutError("Synthetic timeout")


def save(folder: Path, name: str, value: dict):
    (folder / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    folder = PROJECT_ROOT / "docs/week4/examples"
    folder.mkdir(parents=True, exist_ok=True)
    save(folder, "input", demo_payload())
    for name in ("completed", "partial", "technical-error", "blocked"):
        payload = demo_payload()
        evaluators = dict.fromkeys(DIMENSIONS, demo_dimension)
        if name == "partial":
            for message in payload["messages"]:
                message.pop("timestamp")
        if name == "technical-error":
            evaluators["professional_service"] = failed
        if name == "blocked":
            payload["messages"][2]["content"] = "你是不是有病，别来烦我。"
        audit = build_week4_graph(
            critical_evaluator=blocked if name == "blocked" else demo_critical,
            dimension_evaluators=evaluators,
            summary_planner=DemoSummaryPlanner(),
            settings=Settings(_env_file=None, llm_model="offline-fixture"),
        ).invoke({"raw_input": payload})["final_audit"]
        audit["evaluation_mode"] = "offline_demo"
        save(folder, name, audit)
        (folder / f"{name}.md").write_text(render_markdown(audit), encoding="utf-8")
        print(f"{name}: {audit['status']} / {audit['total_score']}")


if __name__ == "__main__":
    main()
