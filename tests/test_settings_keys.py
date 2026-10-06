from customer_service_qa.config import Settings


def test_dashscope_key_from_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DASHSCOPE_API_KEY=test-dashscope\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.has_llm_api_key
    assert settings.llm_api_key.get_secret_value() == "test-dashscope"


def test_key_aliases_preserve_explicit_overrides(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-environment")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert Settings(_env_file=None).llm_api_key.get_secret_value() == "test-environment"
    assert Settings(_env_file=None, llm_api_key=None).has_llm_api_key is False
    assert (
        Settings(_env_file=None, llm_api_key="test-explicit").llm_api_key.get_secret_value()
        == "test-explicit"
    )


def test_legacy_key_takes_precedence(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-legacy")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope")
    assert Settings(_env_file=None).llm_api_key.get_secret_value() == "test-legacy"


def test_thinking_flag_can_be_omitted_or_explicit(monkeypatch):
    monkeypatch.delenv("LLM_ENABLE_THINKING", raising=False)
    assert Settings(_env_file=None).llm_extra_body == {}
    monkeypatch.setenv("LLM_ENABLE_THINKING", "false")
    assert Settings(_env_file=None).llm_extra_body == {"enable_thinking": False}
    assert Settings(_env_file=None, llm_enable_thinking=True).llm_extra_body == {
        "enable_thinking": True
    }
