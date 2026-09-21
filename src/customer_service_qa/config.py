"""Project configuration and versioned rule loaders."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or the local .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "openai_compatible"
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: SecretStr | None = None
    log_level: str = "INFO"
    rule_version: str = "0.1.0"
    prompt_version: str = "0.1.0"

    @property
    def has_llm_api_key(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = yaml.safe_load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return value


@lru_cache(maxsize=1)
def load_preflight_config() -> dict[str, Any]:
    return _load_yaml(PROJECT_ROOT / "configs" / "preflight.yaml")


@lru_cache(maxsize=1)
def load_scoring_config() -> dict[str, Any]:
    return _load_yaml(PROJECT_ROOT / "configs" / "scoring.yaml")


@lru_cache(maxsize=1)
def load_parent_tags() -> frozenset[str]:
    import json

    path = PROJECT_ROOT / "data" / "raw" / "professional-rules.json"
    with path.open(encoding="utf-8") as file:
        rules = json.load(file)
    if not isinstance(rules, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return frozenset(rules)
