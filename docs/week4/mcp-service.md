# 专业规则HTTP MCP服务

使用官方Python MCP SDK 1.30.0（依赖范围mcp>=1.30,<2），FastMCP提供Streamable HTTP协议；不是仅给普通HTTP接口起MCP名字。客户端会完成initialize握手，再调用工具。

协议与SDK参考：[官方Python SDK v1分支](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)。本项目实现及测试以锁定的1.30.0接口为准。

## 启动与调用

终端1，项目根目录：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa.mcp_server --host 127.0.0.1 --port 8765
```

终端2：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --rules-transport mcp --output outputs/week4-mcp-demo.json
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week3/examples/input.json --rules-transport mcp --output outputs/week4-mcp-live.json
```

第一条是固定模型响应，但规则工具通过真实本机HTTP请求；第二条还会调用真实模型。端点默认 `http://127.0.0.1:8765/mcp`，可用--mcp-url或MCP_RULES_URL覆盖。服务窗口按Ctrl+C停止；默认仅监听本机。

## 工具契约

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| get_professional_rules | parent_tag字符串，精确父业务类别 | status=ok与RuleBundle，或status=not_found/UNKNOWN_PARENT_TAG |
| list_categories | 无 | 当前22类业务名称列表 |

RuleBundle含parent_tag、规则源路径、源文件内容版本、每条规则的ID/子项/正文/扣分。原始规则未被复制改写，服务和本地模式共用同一个规则加载器。

rule_gateway.py使用ClientSession和streamable_http_client请求，验证返回类别与结构。未知类型保留业务异常语义；网络/协议/数据异常统一为RuleServiceError，节点转复核。不能在服务失败后默默回退到可能不同版本的本地规则。

规则结果的tool_trace记录transport=mcp、版本、条数和状态。自动测试真的启动本机子进程，执行HTTP握手/工具查询/未知类型，并验证专业Agent从HTTP取得相同规则；不是只mock函数返回。

当前服务是本地开发交付，不含公网认证、反向代理或多租户能力；若后续部署远程服务，需要明确补齐部署与访问控制。
