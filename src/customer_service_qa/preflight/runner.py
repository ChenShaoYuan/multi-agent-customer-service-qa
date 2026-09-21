"""Execute the fourteen deterministic preflight rules defined in week one."""

import re
from datetime import datetime
from typing import Any

from customer_service_qa.config import load_parent_tags, load_preflight_config
from customer_service_qa.schemas import (
    ConversationStats,
    KeywordHit,
    NormalizedConversation,
    PreflightReport,
    SensitiveDataHit,
    TimingViolation,
    TransferEvent,
)
from customer_service_qa.schemas.models import PresenceCheck


def _contains_any(text: str, patterns: list[str]) -> bool:
    lowered = text.casefold()
    return any(pattern.casefold() in lowered for pattern in patterns)


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def _elapsed_seconds(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds())


def run_preflight(
    conversation: NormalizedConversation,
    config: dict[str, Any] | None = None,
    parent_tags: frozenset[str] | None = None,
) -> PreflightReport:
    config = config or load_preflight_config()
    parent_tags = parent_tags or load_parent_tags()
    messages = conversation.messages
    patterns = config["patterns"]

    users = [message for message in messages if message.role == "end-user"]
    agents = [message for message in messages if message.role == "agent"]
    systems = [message for message in messages if message.role == "system"]
    stats = ConversationStats(
        message_count=len(messages),
        user_count=len(users),
        agent_count=len(agents),
        system_count=len(systems),
        turn_count=len(users),
    )

    first_agent = agents[0] if agents else None
    last_agent = agents[-1] if agents else None
    greeting = PresenceCheck(
        evaluable=first_agent is not None,
        present=(
            _contains_any(first_agent.content, patterns["greeting"]) if first_agent else None
        ),
        message_id=first_agent.message_id if first_agent else None,
    )
    closing = PresenceCheck(
        evaluable=last_agent is not None,
        present=_contains_any(last_agent.content, patterns["closing"]) if last_agent else None,
        message_id=last_agent.message_id if last_agent else None,
    )

    timed_messages = [message for message in messages if message.role != "system"]
    timing_available = bool(timed_messages) and all(
        message.timestamp is not None for message in timed_messages
    )
    timing_errors = [warning for warning in conversation.warnings if "timestamp" in warning]
    if timed_messages and not timing_available:
        timing_errors.append("timestamps_missing_for_one_or_more_messages")

    first_response_seconds: float | None = None
    first_response_evaluable = False
    first_response_violation: bool | None = None
    connect_message = next(
        (
            message
            for message in messages
            if message.role == "system"
            and _contains_any(message.content, patterns["connect_agent"])
        ),
        None,
    )
    if connect_message and connect_message.timestamp:
        response = next(
            (
                message
                for message in messages
                if message.role == "agent"
                and message.timestamp
                and message.timestamp >= connect_message.timestamp
            ),
            None,
        )
        if response:
            first_response_evaluable = True
            first_response_seconds = _elapsed_seconds(
                connect_message.timestamp, response.timestamp
            )
            first_response_violation = (
                first_response_seconds > config["timing"]["first_response_max_seconds"]
            )

    response_time_violations: list[TimingViolation] = []
    if timing_available:
        for index, message in enumerate(messages):
            if message.role != "end-user" or message.timestamp is None:
                continue
            response = next(
                (
                    candidate
                    for candidate in messages[index + 1 :]
                    if candidate.role == "agent" and candidate.timestamp is not None
                ),
                None,
            )
            if response is None:
                continue
            elapsed = _elapsed_seconds(message.timestamp, response.timestamp)
            if elapsed > config["timing"]["message_response_max_seconds"]:
                response_time_violations.append(
                    TimingViolation(
                        user_message_id=message.message_id,
                        agent_message_id=response.message_id,
                        elapsed_seconds=elapsed,
                    )
                )

    keyword_hits: list[KeywordHit] = []
    for message in agents:
        for rule_id, keywords in config["redline"]["keywords"].items():
            for keyword in keywords:
                if keyword.casefold() in message.content.casefold():
                    keyword_hits.append(
                        KeywordHit(
                            rule_id=rule_id,
                            keyword=keyword,
                            message_id=message.message_id,
                            context=message.content[:160],
                        )
                    )

    sensitive_hits: list[SensitiveDataHit] = []
    for message in agents:
        for kind, expression in config["sensitive_patterns"].items():
            for match in re.finditer(expression, message.content):
                sensitive_hits.append(
                    SensitiveDataHit(
                        kind=kind,
                        message_id=message.message_id,
                        masked_value=_mask(match.group(0)),
                    )
                )

    tag_warnings: list[str] = []
    if conversation.parent_tag and conversation.parent_tag not in parent_tags:
        tag_warnings.append(f"unknown_parent_tag:{conversation.parent_tag}")

    repeated: list[list[str]] = []
    for previous, current in zip(messages, messages[1:], strict=False):
        if (
            previous.role == current.role == "agent"
            and previous.content.strip().casefold() == current.content.strip().casefold()
        ):
            repeated.append([previous.message_id, current.message_id])

    transfer_events = [
        TransferEvent(
            message_id=message.message_id,
            role=message.role,
            content=message.content[:160],
        )
        for message in messages
        if _contains_any(message.content, patterns["transfer"])
    ]

    input_errors = list(conversation.errors)
    return PreflightReport(
        input_valid=not input_errors and bool(messages),
        input_errors=input_errors,
        role_source=conversation.role_source,
        timing_available=timing_available,
        timing_errors=list(dict.fromkeys(timing_errors)),
        conversation_stats=stats,
        greeting=greeting,
        closing=closing,
        first_response_seconds=first_response_seconds,
        first_response_evaluable=first_response_evaluable,
        first_response_violation=first_response_violation,
        response_time_violations=response_time_violations,
        redline_keyword_hits=keyword_hits,
        sensitive_data_hits=sensitive_hits,
        tag_warnings=tag_warnings,
        repeated_reply_message_ids=repeated,
        transfer_events=transfer_events,
    )
