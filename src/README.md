# Source code

第二周已实现：

- `schemas`：输入、预检、红线与 State 数据契约；
- `adapters`：正式消息和历史样例适配；
- `preflight`：14项确定性预检；
- `agents`：结构化红线主控；
- `graph`：条件路由与阶段结果；
- `cli.py`：本地演示入口。

第三周已增加 `schemas/scoring.py` 数据契约、`agents/dimensions.py` 评分校验、`tools/professional_rules.py` 精确规则查询、`graph/dimension_nodes.py` 独立分支与汇合，以及 `demo.py/reporting.py` 演示与可读结果。详细说明见 `docs/week3/`。

第四周已增加 `schemas/audit.py` 最终契约、`summary.py` 确定性去重及计分、`agents/summary_agent.py` 有限ReAct工具循环、`graph/week4.py` 完整图、`mcp_server.py` 与 `tools/rule_gateway.py` HTTP工具通信、`observability.py` 最小事件日志、`evaluation.py` 断点跑批。默认CLI运行第四周，设计、边界与真实效果见 `docs/week4/`。
