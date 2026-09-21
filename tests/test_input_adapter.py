import json

from customer_service_qa.adapters import normalize_input
from customer_service_qa.config import PROJECT_ROOT


def test_structured_messages_are_normalized() -> None:
    payload = {
        "ticket_id": "T-1",
        "tag": "账户-登录异常",
        "parent_tag": "账户安全",
        "messages": [
            {
                "role": "user",
                "content": "无法登录",
                "timestamp": "2026-09-22T10:00:00+08:00",
            },
            {
                "role": "assistant",
                "content": "您好，请提供报错信息",
                "timestamp": "2026-09-22T10:00:30+08:00",
            },
        ],
    }

    result = normalize_input(payload)

    assert not result.errors
    assert result.role_source == "provided"
    assert [message.role for message in result.messages] == ["end-user", "agent"]
    assert result.messages[0].message_id == "m001"


def test_legacy_comments_infer_alternating_roles() -> None:
    payload = {
        "ticketId": 1,
        "tag": "账户-登录异常",
        "parentTag": "账户安全",
        "comments": "用户消息\n客服消息\n用户追问\n客服答复",
    }

    result = normalize_input(payload)

    assert result.role_source == "inferred"
    assert [message.role for message in result.messages] == [
        "end-user",
        "agent",
        "end-user",
        "agent",
    ]
    assert "roles_inferred_from_legacy_alternating_lines" in result.warnings


def test_all_bundled_samples_can_be_normalized() -> None:
    path = PROJECT_ROOT / "data" / "raw" / "sample-conversations.json"
    samples = json.loads(path.read_text(encoding="utf-8"))

    results = [normalize_input(sample) for sample in samples]

    assert len(results) == 100
    assert all(result.messages for result in results)
    assert all(not result.errors for result in results)


def test_empty_payload_produces_explicit_errors() -> None:
    result = normalize_input({})

    assert "missing_ticket_id" in result.errors
    assert "missing_conversation_messages" in result.errors
