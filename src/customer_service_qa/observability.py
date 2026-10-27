"""Append local structured alerts without copying dialogue, evidence, or credentials."""

import json
from datetime import UTC, datetime
from pathlib import Path


def write_audit_event(audit: dict, path: Path) -> None:
    event = {
        "at": datetime.now(UTC).isoformat(),
        "audit_id": audit.get("audit_id"),
        "status": audit["status"],
        "grade": audit["grade"],
        "total_score": audit.get("total_score"),
        "alerts": [
            {"code": a["code"], "severity": a["severity"], "node": a["node"]}
            for a in audit.get("alerts", [])
        ],
        "nodes": [
            {
                key: t.get(key)
                for key in (
                    "node",
                    "status",
                    "duration_ms",
                    "retry_count",
                    "model_name",
                    "rule_version",
                    "prompt_version",
                )
            }
            for t in audit.get("trace", [])
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
