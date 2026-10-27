"""Local and MCP clients share one exact-rule contract; no silent remote fallback."""

import asyncio
import json
from datetime import timedelta

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from customer_service_qa.config import Settings
from customer_service_qa.schemas.scoring import RuleBundle
from customer_service_qa.tools.professional_rules import (
    UnknownCategoryError,
    get_professional_rules,
)


class RuleServiceError(RuntimeError):
    """The selected remote rule source was unavailable or violated its contract."""


async def call_mcp_tool(url: str, name: str, arguments: dict, timeout: float = 10):
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with streamable_http_client(url, http_client=client) as (reader, writer, _):
                async with ClientSession(
                    reader, writer, read_timeout_seconds=timedelta(seconds=timeout)
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    if result.isError:
                        raise RuleServiceError("MCP tool reported an error")
                    if result.structuredContent is not None:
                        return result.structuredContent
                    blocks = [block.text for block in result.content if block.type == "text"]
                    if len(blocks) != 1:
                        raise RuleServiceError("MCP tool returned an invalid response")
                    return json.loads(blocks[0])


def get_mcp_rules(parent_tag: str, settings: Settings) -> RuleBundle:
    try:
        response = asyncio.run(
            call_mcp_tool(
                settings.mcp_rules_url,
                "get_professional_rules",
                {"parent_tag": parent_tag},
                settings.mcp_timeout_seconds,
            )
        )
        if response.get("status") == "not_found":
            raise UnknownCategoryError("Unknown parent tag")
        if response.get("status") != "ok":
            raise RuleServiceError("Invalid MCP rule status")
        bundle = RuleBundle.model_validate(response["bundle"])
        if bundle.parent_tag != parent_tag or not bundle.rules:
            raise RuleServiceError("MCP rule category mismatch")
        return bundle
    except UnknownCategoryError:
        raise
    except Exception:
        raise RuleServiceError("MCP rule service failed") from None


def get_rule_lookup(settings: Settings):
    if settings.rules_transport == "mcp":
        return lambda parent_tag: get_mcp_rules(parent_tag, settings)
    return get_professional_rules
