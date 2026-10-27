import asyncio
import os
import socket
import subprocess
import sys
import time

import pytest
from test_week4_summary import graph4

from customer_service_qa.config import PROJECT_ROOT, Settings
from customer_service_qa.demo import demo_payload
from customer_service_qa.tools.professional_rules import (
    UnknownCategoryError,
    get_professional_rules,
)
from customer_service_qa.tools.rule_gateway import call_mcp_tool, get_mcp_rules


@pytest.fixture(scope="module")
def mcp_url():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.Popen(
        [sys.executable, "-m", "customer_service_qa.mcp_server", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("MCP server exited before readiness")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("MCP server did not become ready")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_real_http_mcp_handshake_tool_and_exact_rules(mcp_url):
    settings = Settings(_env_file=None, mcp_rules_url=mcp_url, rules_transport="mcp")
    result = get_mcp_rules("账户安全", settings)
    assert result.model_dump() == get_professional_rules("账户安全").model_dump()
    categories = asyncio.run(call_mcp_tool(mcp_url, "list_categories", {}))
    assert len(categories["result"] if isinstance(categories, dict) else categories) == 22
    with pytest.raises(UnknownCategoryError):
        get_mcp_rules("未收录类别", settings)


def test_week4_professional_agent_uses_http_rules(mcp_url):
    settings = Settings(_env_file=None, mcp_rules_url=mcp_url, rules_transport="mcp")
    audit = graph4(settings=settings).invoke({"raw_input": demo_payload()})["final_audit"]
    assert audit["status"] == "completed" and audit["total_score"] == 96
    assert audit["dimensions"]["professional_service"]["tool_trace"][0]["transport"] == "mcp"
