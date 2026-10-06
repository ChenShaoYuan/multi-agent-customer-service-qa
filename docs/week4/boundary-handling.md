# 异常边界、降级与告警

| 触发情况 | 程序行为 | 告警/状态 |
| --- | --- | --- |
| 输入为空、非对象、规范化抛错 | guarded_node捕获，后续不发有效评分请求 | PREFLIGHT_INVALID / manual_review |
| 预检缺失或无效 | 汇总契约检查阻止总分 | PREFLIGHT_INVALID |
| 主控解析失败、空响应、超时 | 最多2次，未放行就短路 | GATE_INVALID |
| 红线命中 | 不运行三维，保留红线证据 | REDLINE_TRIGGERED / blocked |
| 某维度超时或格式失败 | 最多2次，保留另外两维 | DIMENSION_INCOMPLETE |
| 子维度缺失/总分与子项不一致 | 汇总拒绝使用 | DIMENSION_INVALID |
| 时间戳缺失、倒序、未回复消息 | 时效不可评，不补满分也不扣业务0分 | partial → manual_review |
| 未知父类型 | 不调用专业模型 | manual_review |
| MCP服务不可达、协议错误 | 不偷偷换成本地规则；专业分技术失败 | DIMENSION_INCOMPLETE |
| 聚合调用失败、工具参数不合法 | 有限ReAct循环，耗尽保留原始结果 | SUMMARY_EXHAUSTED |
| 聚合未预期异常 | 不输出总分 | SUMMARY_ERROR |
| 某次失败但重试成功 | 允许完成，保留失败轨迹 | NODE_ATTEMPT_FAILED / warning |

所有第四周分支统一使用FinalAudit字段结构：status、grade、total_score、dimensions、feedback、alerts、trace等。blocked/manual_review的total_score必须null；原始任务提及的“兜底0”只在维度fallback_score中表示技术占位。

`--log-output logs/audit-events.jsonl`会追加结构化事件：audit_id、状态、总分、告警代码、节点耗时和版本，不记录对话、ticket_id、证据、API Key或完整异常正文。它是本地告警记录，不发送邮件/Slack，不是已部署的外部监控系统。

SDK额外重试关闭，节点级重试有明确上限；批量最多4条会话并发、默认2条。模型请求超时不是整图硬截止时间；连续多次请求的总时间可能更长。MCP请求用独立总超时控制。批量每条结果独立落盘，可重启续跑，但当前没有通用LangGraph checkpoint恢复任意节点功能。
