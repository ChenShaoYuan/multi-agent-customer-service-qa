import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_raw_dataset_contract() -> None:
    sample_path = PROJECT_ROOT / "data" / "raw" / "sample-conversations.json"
    samples = json.loads(sample_path.read_text(encoding="utf-8"))

    assert len(samples) == 100
    assert all(
        {"ticketId", "messages", "comments", "tag", "parentTag"} <= sample.keys()
        for sample in samples
    )


def test_professional_rule_categories() -> None:
    rules_path = PROJECT_ROOT / "data" / "raw" / "professional-rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))

    assert len(rules) == 22
    assert all(isinstance(name, str) and isinstance(rule, str) for name, rule in rules.items())


def test_scoring_configuration_is_consistent() -> None:
    config_path = PROJECT_ROOT / "configs" / "scoring.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dimensions = config["dimensions"]

    assert sum(item["weight"] for item in dimensions.values()) == 100
    assert dimensions["service_process"]["raw_max_score"] == 25
    assert dimensions["professional_service"]["raw_max_score"] == 50
    assert dimensions["communication"]["raw_max_score"] == 25
    assert config["policies"]["technical_error_as_zero_score"] is False


def test_preflight_configuration_is_consistent() -> None:
    config_path = PROJECT_ROOT / "configs" / "preflight.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["timing"]["first_response_max_seconds"] == 90
    assert config["timing"]["message_response_max_seconds"] == 300
    assert len(config["checks"]) == 14
    assert config["redline"]["keyword_hit_is_final_decision"] is False
