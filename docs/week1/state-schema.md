# State 数据结构规范

## 1. 设计原则

1. 所有节点读写同一份逻辑 State。
2. 节点只返回它负责更新的字段。
3. 原始输入、业务结果和技术错误分开保存。
4. 并行节点写不同字段。
5. 对外只返回 `final_audit`，调用方不拼接中间状态。

## 2. 概念结构

```python
from typing import Literal, TypedDict


class Message(TypedDict):
    message_id: str
    role: Literal["end-user", "agent", "system"]
    content: str
    timestamp: str | None


class AuditState(TypedDict, total=False):
    audit_id: str
    ticket_id: str
    tag: str
    parent_tag: str
    raw_input: dict
    messages: list[Message]
    role_source: Literal["provided", "inferred"]

    rule_version: str
    prompt_version: str
    model_name: str

    input_warnings: list[dict]
    preflight_report: dict
    redline_result: dict
    gate_status: Literal["pass", "blocked", "review"]

    service_process_result: dict
    professional_service_result: dict
    communication_result: dict

    node_traces: dict[str, dict]
    technical_errors: list[dict]
    final_audit: dict
```

第二周使用 Pydantic 定义实际输入输出模型；这里的 `TypedDict` 用于确认 LangGraph 共享字段和节点边界。

## 3. 字段说明

| 字段 | 写入节点 | 必填时点 | 说明 |
|---|---|---|---|
| `audit_id` | 入口 | 开始 | 单次质检唯一编号 |
| `ticket_id` | 入口 | 开始 | 业务工单编号 |
| `tag/parent_tag` | 入口 | 开始 | 子标签和专业规则分类 |
| `raw_input` | 入口 | 开始 | 审计用原始数据，日志前脱敏 |
| `messages` | 输入规范化 | 规范化后 | 后续节点唯一使用的标准消息 |
| `role_source` | 输入规范化 | 规范化后 | 角色由输入提供或适配器推断 |
| `*_version` | 入口 | 模型调用前 | 保证结果可复现和追踪 |
| `preflight_report` | 预检 | 主控前 | 确定性事实和风险线索 |
| `redline_result` | 主控 | 路由前 | 四类红线结论、原因和证据 |
| `gate_status` | 主控 | 路由前 | `pass/blocked/review` |
| 三个评分结果 | 三个评分节点 | 汇总前 | 各维度原始分和扣分项 |
| `technical_errors` | 任意节点 | 有错误时 | 与业务扣分完全分离 |
| `node_traces` | 汇总 | 结束 | 节点耗时、版本和状态 |
| `final_audit` | 汇总 | 结束 | 唯一对外结果 |

## 4. 公共扣分项

```json
{
  "rule_id": "PS-ACCOUNT-01",
  "issue_id": "issue-001",
  "result": "deducted",
  "deduction": 10,
  "reason": "客服未引导用户立即修改密码",
  "evidence_message_ids": ["m2", "m4"]
}
```

约束：

- `rule_id` 必须存在于当前规则版本。
- `deduction` 不得为负数且不能超过子项满分。
- 证据编号必须存在于 `messages`。
- 相同问题在多个维度出现时复用同一 `issue_id`。

## 5. 正式输入契约

```json
{
  "ticket_id": "10001",
  "tag": "账户-登录异常",
  "parent_tag": "账户安全",
  "messages": [
    {
      "message_id": "m1",
      "role": "end-user",
      "content": "你好，我的账户无法登录。",
      "timestamp": "2026-09-20T10:00:00+08:00"
    }
  ]
}
```

## 6. 最终输出关键字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `audit_id` | string | 质检编号 |
| `ticket_id` | string | 工单编号 |
| `status` | enum | `completed/blocked/manual_review` |
| `redline` | object | 是否触发、规则、原因和证据 |
| `dimensions` | object/null | 三维原始分、加权分和扣分项 |
| `total_score` | number/null | 0—100；红线或人工复核时为空 |
| `grade` | enum | 优秀、合格、严重问题、严重不合格、待人工复核 |
| `manual_review_reasons` | array | 需要人工处理的原因 |
| `trace` | array | 节点执行摘要 |

