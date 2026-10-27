"""Official MCP Streamable HTTP rule service, bound to localhost by default."""

import argparse

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from customer_service_qa.schemas.scoring import RuleBundle
from customer_service_qa.tools.professional_rules import (
    UnknownCategoryError,
    get_professional_rules,
    load_rule_catalog,
)


class RuleToolReply(BaseModel):
    status: str
    bundle: RuleBundle | None = None
    error_code: str | None = None


def create_server(host="127.0.0.1", port=8765):
    server = FastMCP(
        "customer-service-professional-rules",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        log_level="WARNING",
    )

    @server.tool(name="get_professional_rules")
    def lookup(parent_tag: str) -> RuleToolReply:
        """按精确父业务类型查询专业规则，返回条款ID、扣分、免责和规则源版本。"""
        try:
            return RuleToolReply(status="ok", bundle=get_professional_rules(parent_tag))
        except UnknownCategoryError:
            return RuleToolReply(status="not_found", error_code="UNKNOWN_PARENT_TAG")

    @server.tool()
    def list_categories() -> list[str]:
        """列出当前规则服务支持的全部父业务类型。"""
        return sorted(load_rule_catalog())

    return server


def main():
    parser = argparse.ArgumentParser(description="Serve professional rules over MCP HTTP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    create_server(args.host, args.port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
