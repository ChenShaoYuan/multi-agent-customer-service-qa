"""Project configuration and versioned rule loaders."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or the local .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    llm_provider: str = "openai_compatible"
    llm_model: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_API_KEY", "DASHSCOPE_API_KEY"),
    )
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_enable_thinking: bool | None = None
    log_level: str = "INFO"
    rule_version: str = "0.1.0"
    prompt_version: str = "0.3.0"
    rules_transport: Literal["local", "mcp"] = "local"
    mcp_rules_url: str = "http://127.0.0.1:8765/mcp"
    mcp_timeout_seconds: float = Field(default=10, gt=0, le=60)
    summary_max_steps: int = Field(default=4, ge=2, le=6)

    @property
    def has_llm_api_key(self) -> bool:
        return bool(self.llm_api_key and self.llm_api_key.get_secret_value().strip())

    @property
    def llm_extra_body(self) -> dict[str, bool]:
        if self.llm_enable_thinking is None:
            return {}
        return {"enable_thinking": self.llm_enable_thinking}


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
def load_dimension_rubrics() -> dict[str, Any]:
    return _load_yaml(PROJECT_ROOT / "configs" / "dimension-rubrics.yaml")


@lru_cache(maxsize=1)
def load_summary_config() -> dict[str, Any]:
    return _load_yaml(PROJECT_ROOT / "configs" / "summary.yaml")


@lru_cache(maxsize=1)
def load_parent_tags() -> frozenset[str]:
    import json

    path = PROJECT_ROOT / "data" / "raw" / "professional-rules.json"
    with path.open(encoding="utf-8") as file:
        rules = json.load(file)
    if not isinstance(rules, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return frozenset(rules)
