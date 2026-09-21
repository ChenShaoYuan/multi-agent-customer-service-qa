"""Normalize supported request shapes into one validated conversation model."""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from customer_service_qa.schemas import Message, NormalizedConversation

ROLE_ALIASES = {
    "end-user": "end-user",
    "user": "end-user",
    "customer": "end-user",
    "agent": "agent",
    "assistant": "agent",
    "customer-service": "agent",
    "system": "system",
}


def _value(payload: Mapping[str, Any], snake: str, camel: str) -> Any:
    return payload.get(snake, payload.get(camel))


def _required_text(value: Any, field: str, errors: list[str]) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        errors.append(f"missing_{field}")
    return text


def _structured_messages(
    raw_messages: list[Any], errors: list[str], warnings: list[str]
) -> list[Message]:
    messages: list[Message] = []
    for index, raw_message in enumerate(raw_messages, start=1):
        if not isinstance(raw_message, Mapping):
            errors.append(f"message_{index}_must_be_an_object")
            continue

        raw_role = str(raw_message.get("role", "")).strip().lower()
        role = ROLE_ALIASES.get(raw_role)
        if role is None:
            errors.append(f"message_{index}_invalid_role:{raw_role or 'missing'}")
            continue

        content = str(raw_message.get("content", "")).strip()
        if not content:
            errors.append(f"message_{index}_empty_content")
            continue

        message_id = str(raw_message.get("message_id") or f"m{index:03d}").strip()
        timestamp = raw_message.get("timestamp")
        try:
            messages.append(
                Message(
                    message_id=message_id,
                    role=role,
                    content=content,
                    timestamp=timestamp,
                )
            )
        except ValidationError:
            warnings.append(f"message_{index}_invalid_timestamp")
            messages.append(
                Message(
                    message_id=message_id,
                    role=role,
                    content=content,
                    timestamp=None,
                )
            )
    return messages


def _legacy_messages(comments: str) -> list[Message]:
    lines = [line.strip() for line in comments.splitlines() if line.strip()]
    return [
        Message(
            message_id=f"m{index:03d}",
            role="end-user" if index % 2 == 1 else "agent",
            content=line,
            timestamp=None,
        )
        for index, line in enumerate(lines, start=1)
    ]


def normalize_input(payload: Mapping[str, Any]) -> NormalizedConversation:
    """Normalize production messages or the repository's legacy comments field."""

    errors: list[str] = []
    warnings: list[str] = []
    ticket_id = _required_text(_value(payload, "ticket_id", "ticketId"), "ticket_id", errors)
    tag = _required_text(payload.get("tag"), "tag", errors)
    parent_tag = _required_text(
        _value(payload, "parent_tag", "parentTag"), "parent_tag", errors
    )

    raw_messages = payload.get("messages")
    if isinstance(raw_messages, list) and raw_messages:
        messages = _structured_messages(raw_messages, errors, warnings)
        role_source = "provided"
    else:
        comments = str(payload.get("comments") or "").strip()
        messages = _legacy_messages(comments) if comments else []
        role_source = "inferred"
        if messages:
            warnings.append("roles_inferred_from_legacy_alternating_lines")

    if not messages:
        errors.append("missing_conversation_messages")

    return NormalizedConversation(
        ticket_id=ticket_id,
        tag=tag,
        parent_tag=parent_tag,
        messages=messages,
        role_source=role_source,
        warnings=warnings,
        errors=list(dict.fromkeys(errors)),
    )
