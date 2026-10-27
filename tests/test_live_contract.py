from test_dimension_scoring import context_for

from customer_service_qa.agents.dimensions import LiveDimensionEvaluator
from customer_service_qa.config import Settings
from customer_service_qa.demo import demo_dimension
from customer_service_qa.schemas.scoring import DimensionAssessment


def test_live_adapter_passes_specialist_rules_to_structured_model(monkeypatch):
    captured = {}
    context = context_for("professional_service")

    class FakeChat:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs

        def with_structured_output(self, schema, method):
            assert schema is DimensionAssessment and method == "function_calling"
            return self

        def invoke(self, messages):
            captured["messages"] = messages
            return DimensionAssessment.model_validate(demo_dimension(context))

    monkeypatch.setattr("customer_service_qa.agents.dimensions.ChatOpenAI", FakeChat)
    result = LiveDimensionEvaluator(
        Settings(
            _env_file=None,
            llm_api_key="test-placeholder",
            llm_timeout_seconds=12,
            llm_enable_thinking=False,
        )
    )(context)
    assert result.dimension == "professional_service"
    assert captured["settings"]["timeout"] == 12 and captured["settings"]["max_retries"] == 0
    assert captured["settings"]["extra_body"] == {"enable_thinking": False}
    assert "你负责专业服务" in captured["messages"][0].content
    assert context.professional_rules.rules[0].rule_id in captured["messages"][1].content
    assert "PS-01" in captured["messages"][1].content


def test_redline_adapter_also_disables_thinking_when_configured(monkeypatch):
    from customer_service_qa.adapters import normalize_input
    from customer_service_qa.agents.critical import LiveCriticalEvaluator
    from customer_service_qa.demo import demo_critical, demo_payload
    from customer_service_qa.preflight import run_preflight
    from customer_service_qa.schemas import RedlineAssessment

    captured = {}
    conversation = normalize_input(demo_payload())
    preflight = run_preflight(conversation)

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def with_structured_output(self, schema, method):
            assert schema is RedlineAssessment and method == "function_calling"
            return self

        def invoke(self, messages):
            return demo_critical(conversation.messages, preflight)

    monkeypatch.setattr("customer_service_qa.agents.critical.ChatOpenAI", FakeChat)
    LiveCriticalEvaluator(
        Settings(_env_file=None, llm_api_key="test-placeholder", llm_enable_thinking=False)
    )(conversation.messages, preflight)
    assert captured["extra_body"] == {"enable_thinking": False}
