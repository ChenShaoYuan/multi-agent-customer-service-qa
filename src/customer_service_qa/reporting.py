"""Render a readable week-three report from validated graph output."""


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>").replace("\r", "")


def render_markdown(audit: dict) -> str:
    total = audit.get("total_score")
    lines = [
        "# 客服质检结果",
        "",
        f"工单：{_cell(audit.get('ticket_id', ''))}",
        f"状态：{audit['status']}；评级：{audit['grade']}",
        "",
        (
            f"最终总分：{total if total is not None else 'N/A'} / 100"
            if audit.get("week") == 4
            else "第三周仅输出各维度原始分，尚未计算加权总分和最终评级。"
        ),
        "",
    ]
    if audit.get("evaluation_mode") == "offline_demo":
        lines += ["> 此结果由合成对话和固定模型响应生成，仅用于演示和工程测试。", ""]
    for name, result in audit.get("dimensions", {}).items():
        lines += [
            f"## {name}：{result['score_text']}（{result['status']}）",
            "",
            "| 子项 | 分数 | 原因 | 条款 | 对话原文 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in result["items"]:
            rules = "; ".join(
                f"{rule}: {text}"
                for rule, text in zip(item["rule_ids"], item["rule_texts"], strict=True)
            )
            quotes = "; ".join(f"{e['message_id']}: {e['quote']}" for e in item["evidence"])
            row = [item["item_id"], item["score_text"], item["reason"], rules, quotes]
            lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
        if result["fallback_score"] is not None:
            lines += ["", "技术兜底分为0；有效业务分仍为空，需要人工复核。"]
        lines.append("")
    if audit.get("manual_review_reasons"):
        lines += [
            "## 待复核原因",
            "",
            *[f"- {_cell(reason)}" for reason in audit["manual_review_reasons"]],
            "",
        ]
    if audit.get("week") == 4:
        lines += [
            "## 权重与去重后的得分",
            "",
            "各维度上表保留原始评分；以下分数在去重后参与总分计算。",
            "",
            "| 维度 | 调整后原始分 | 加权贡献 |",
            "| --- | --- | --- |",
        ]
        for name, raw in audit.get("adjusted_raw_scores", {}).items():
            lines.append(f"| {name} | {raw} | {audit['weighted_scores'][name]} |")
        lines += ["", "## 改进建议", ""]
        lines.extend(
            f"- {_cell(f['advice'])}（子项：{', '.join(f['item_ids']) or '整体'}）"
            for f in audit.get("feedback", [])
        )
        for resolution in audit.get("duplicate_resolutions", []):
            lines += [
                "",
                f"去重 {resolution['issue_id']}：保留{resolution['kept_finding_id']}；"
                f"恢复{', '.join(resolution['restored_finding_ids'])}。"
                f"{_cell(resolution['reason'])}",
            ]
        if audit.get("alerts"):
            lines += ["", "## 告警与数据边界", ""]
            lines.extend(
                f"- [{a['severity']}] {a['code']}：{_cell(a['message'])}" for a in audit["alerts"]
            )
        if audit.get("react_steps"):
            lines += ["", "## 汇总工具调用记录", ""]
            lines.extend(
                f"- 第{s['step']}轮：{s['action']} → {s['status']}" for s in audit["react_steps"]
            )
    return "\n".join(lines) + "\n"
