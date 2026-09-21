"""Command-line entry point for preflight inspection and live redline execution."""

import argparse
import json
from pathlib import Path
from typing import Any

from customer_service_qa.adapters import normalize_input
from customer_service_qa.config import PROJECT_ROOT, Settings
from customer_service_qa.graph import build_week2_graph
from customer_service_qa.preflight import run_preflight


def _load_payload(input_path: Path | None, sample_index: int | None) -> dict[str, Any]:
    path = input_path or PROJECT_ROOT / "data" / "raw" / "sample-conversations.json"
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        if sample_index is None:
            raise ValueError("JSON contains a list; provide --sample-index")
        return payload[sample_index]
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object or a list of objects")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the week-two quality-audit workflow")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Path to a JSON request")
    source.add_argument("--sample-index", type=int, help="Index in the bundled sample dataset")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run deterministic normalization and preflight without an LLM call",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = _load_payload(args.input, args.sample_index)
    if args.preflight_only:
        conversation = normalize_input(payload)
        output = {
            "normalized": conversation.model_dump(mode="json"),
            "preflight": run_preflight(conversation).model_dump(mode="json"),
        }
    else:
        result = build_week2_graph(settings=Settings()).invoke({"raw_input": payload})
        output = result["final_audit"]
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0
