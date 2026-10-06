"""CLI for offline demonstrations, deterministic preflight, and live week-two/three audits."""

import argparse
import json
from pathlib import Path
from typing import Any

from customer_service_qa.adapters import normalize_input
from customer_service_qa.agents.summary_agent import DemoSummaryPlanner
from customer_service_qa.config import PROJECT_ROOT, Settings
from customer_service_qa.graph import build_week2_graph, build_week3_graph, build_week4_graph
from customer_service_qa.observability import write_audit_event
from customer_service_qa.preflight import run_preflight
from customer_service_qa.reporting import render_markdown
from customer_service_qa.schemas.scoring import DIMENSIONS


def _load_payload(input_path: Path | None, sample_index: int | None) -> dict[str, Any]:
    path = input_path or PROJECT_ROOT / "data" / "raw" / "sample-conversations.json"
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if isinstance(payload, list):
        if sample_index is None:
            raise ValueError("JSON contains a list; provide --sample-index")
        if not 0 <= sample_index < len(payload):
            raise ValueError("Sample index is outside the dataset")
        payload = payload[sample_index]
    if not isinstance(payload, dict):
        raise ValueError("Input JSON must be an object or a list of objects")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the customer-service quality-audit workflow")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Path to a JSON request")
    source.add_argument("--sample-index", type=int, help="Index in the bundled sample dataset")
    source.add_argument("--demo", action="store_true", help="Synthetic offline demonstration")
    parser.add_argument("--week", type=int, choices=[2, 3, 4], default=4)
    parser.add_argument("--rules-transport", choices=["local", "mcp"])
    parser.add_argument("--mcp-url", help="MCP rule server URL, default http://127.0.0.1:8765/mcp")
    parser.add_argument("--log-output", type=Path, help="Append a sanitized audit event JSONL")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", type=Path, help="Save report as UTF-8")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run deterministic normalization and preflight without an LLM call",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.demo and (args.week == 2 or args.preflight_only):
        parser.error("--demo requires week 3 or 4 and cannot be combined with --preflight-only")
    if args.preflight_only and args.format != "json":
        parser.error("--preflight-only supports JSON output")
    if args.demo:
        from customer_service_qa.demo import demo_critical, demo_dimension, demo_payload

        payload = demo_payload()
    else:
        try:
            payload = _load_payload(args.input, args.sample_index)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    if args.preflight_only:
        conversation = normalize_input(payload)
        output = {
            "normalized": conversation.model_dump(mode="json"),
            "preflight": run_preflight(conversation).model_dump(mode="json"),
        }
    else:
        settings_kwargs = {}
        if args.rules_transport:
            settings_kwargs["rules_transport"] = args.rules_transport
        if args.mcp_url:
            settings_kwargs["mcp_rules_url"] = args.mcp_url
        if args.demo:
            builder = build_week3_graph if args.week == 3 else build_week4_graph
            graph = builder(
                critical_evaluator=demo_critical,
                dimension_evaluators={name: demo_dimension for name in DIMENSIONS},
                settings=Settings(llm_model="offline-fixture", **settings_kwargs),
                **({"summary_planner": DemoSummaryPlanner()} if args.week == 4 else {}),
            )
        else:
            builder = {2: build_week2_graph, 3: build_week3_graph, 4: build_week4_graph}[args.week]
            graph = builder(settings=Settings(**settings_kwargs))
        result = graph.invoke({"raw_input": payload})
        output = result["final_audit"]
        output["evaluation_mode"] = "offline_demo" if args.demo else "live"
        if args.log_output:
            write_audit_event(output, args.log_output)
    rendered = (
        render_markdown(output)
        if args.format == "markdown"
        else json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0
