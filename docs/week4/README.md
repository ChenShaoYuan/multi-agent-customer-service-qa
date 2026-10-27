# 第四周交付：完整客服质检流程

本周按原始要求完成五项交付，保留第二、三周入口，默认CLI运行完整第四周版本。

| 原始任务 | 实现 | 可审阅交付 |
| --- | --- | --- |
| ReAct汇总节点与业务权重 | `agents/summary_agent.py`、`summary.py`、`graph/week4.py` | [聚合与评分方案](summary-agent.md) |
| 分数段评级与建议 | `grade_score()`、`apply_summary()`、`configs/summary.yaml` | [评级与反馈](grading-feedback.md) |
| 异常降级和告警 | `schemas/audit.py`、`guarded_node()`、`observability.py` | [边界处理](boundary-handling.md) |
| 按类型查规则的HTTP MCP服务 | `mcp_server.py`、`tools/rule_gateway.py` | [MCP服务说明](mcp-service.md) |
| 历史数据端到端效果测试 | `evaluation.py`、规则参考集、真实模型跑批 | [效果报告](evaluation-report.md) |

完整验收与复现入口见 [项目验收](acceptance.md)。

## 快速运行

在项目根目录运行无需模型密钥的完整演示：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --output outputs/week4-demo.json
.\.venv\Scripts\python.exe -m customer_service_qa --demo --format markdown --output outputs/week4-demo.md
```

固定演示服务流程20/25、专业50/50、沟通25/25，权重换算96分，评级优秀。它使用脚本化工具决策，不证明真实模型效果。

当前已配置的真实接口运行：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --input docs/week3/examples/input.json --week 4 --output outputs/week4-live.json --log-output logs/audit-events.jsonl
```

默认本地规则查询。需要验证完整HTTP MCP链路时，按MCP说明先启动服务，再追加 `--rules-transport mcp`。

`completed`有有效总分；`blocked`为严重不合格、无三维总分；`manual_review`保留有效证据与原始分，禁止把技术0分或缺资料填入总分。
