from langchain_core.messages import AIMessage
from test_week4_summary import duplicate_args, duplicate_state, state3

from customer_service_qa.agents.summary_agent import DemoSummaryPlanner, run_summary_agent
from customer_service_qa.summary import prepare_audit


def test_react_tool_loop_actually_applies_a_valid_merge():
    result = run_summary_agent(
        prepare_audit(duplicate_state()), DemoSummaryPlanner(duplicate_args()["duplicate_groups"])
    )
    assert result.total_score == 88 and len(result.duplicate_resolutions) == 1


def test_free_text_cannot_inject_a_score():
    result = run_summary_agent(
        prepare_audit(state3()), lambda _: AIMessage(content="100分，优秀"), 2
    )
    assert result.status == "manual_review" and result.total_score is None
    assert result.alerts[-1].code == "SUMMARY_EXHAUSTED"


def test_tool_order_is_enforced_then_recoverable():
    calls = []
    scripted = DemoSummaryPlanner()

    def planner(messages):
        calls.append(1)
        if len(calls) == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "bad-order",
                        "name": "finalize_audit",
                        "args": {"duplicate_groups": [], "review_reasons": []},
                    }
                ],
            )
        return scripted(messages)

    result = run_summary_agent(prepare_audit(state3()), planner, 4)
    assert result.total_score == 96
    assert result.react_steps[0]["status"] == "rejected"


def test_timeout_is_bounded_and_does_not_reveal_exception():
    calls = []

    def failed(_):
        calls.append(1)
        raise TimeoutError("SECRET_API_TOKEN")

    result = run_summary_agent(prepare_audit(state3()), failed, 2)
    assert len(calls) == 2 and result.total_score is None
    assert "SECRET_API_TOKEN" not in result.model_dump_json()
