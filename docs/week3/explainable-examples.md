# 可解释结果示例

这些文件通过真实LangGraph运行合成输入和固定响应生成，验证工程链路，不代表模型准确率。

| 文件 | 内容 |
| --- | --- |
| [input.json](examples/input.json) | 完整合成会话 |
| [completed.md](examples/completed.md) | 可读评分表：分数、原因、规则、原文 |
| [completed.json](examples/completed.json) | 三维结果及7条轨迹 |
| [partial.json](examples/partial.json) | 去掉时间戳，两个时效项不可评 |
| [technical-error.json](examples/technical-error.json) | 专业模型两次超时，其余结果保留 |
| [blocked.json](examples/blocked.json) | m003换成明确辱骂、预设CR-02触发，跳过评分 |

完整示例：服务流程20/25、专业50/50、沟通25/25。SP-01扣5：仅问好并提供方案，缺少完整欢迎表达。这是人工固定答案示例，真实模型结论须另行验证。

逐项阅读顺序：`item_id`标准 → `score_text/deduction`分值 → `reason`理由 → `rule_ids/rule_texts`规则 → `evidence.message_id/quote`对话原文。

重生成全部示例（UUID/时间会变化）：

```powershell
.\.venv\Scripts\python.exe scripts/generate_week3_examples.py
```

只生成可读报告：

```powershell
.\.venv\Scripts\python.exe -m customer_service_qa --demo --format markdown --output outputs/week3-demo.md
```

`reporting.py`只排版验证后的结果，不重新评分，也不计算第四周总分。
