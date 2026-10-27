"""Explicit synthetic fixtures for offline plumbing demos, never a live scoring substitute."""

from customer_service_qa.schemas import RedlineAssessment, RedlineFinding


def demo_payload() -> dict:
    rows = [
        ("system", "正在连接客服", "00"),
        ("end-user", "我的账户无法登录，提示密码错误。", "10"),
        ("agent", "您好，请先使用登录页的忘记密码功能立即重置密码。", "30"),
        ("end-user", "重置后已经可以登录，问题解决了。", "40"),
        ("agent", "感谢您的反馈，祝您生活愉快，再见。", "50"),
    ]
    return {
        "ticket_id": "DEMO-W3-001",
        "parent_tag": "账户安全",
        "tag": "账户-登录异常",
        "messages": [
            {
                "message_id": f"m{i:03d}",
                "role": role,
                "content": content,
                "timestamp": f"2026-09-27T10:00:{second}+08:00",
            }
            for i, (role, content, second) in enumerate(rows, 1)
        ],
    }


def demo_critical(_messages, _preflight) -> RedlineAssessment:
    return RedlineAssessment(
        items=[
            RedlineFinding(rule_id=rule, triggered=False, reason="离线示例预设无红线。")
            for rule in ("CR-01", "CR-02", "CR-03", "CR-04")
        ],
        summary="离线演示：固定返回值，仅验证工作流。",
    )


def demo_dimension(context) -> dict:
    # These item answers apply ONLY to demo_payload; do not classify real conversations here.
    reasons = {
        "SP-01": "仅问好并直接提供方案，缺少完整欢迎语，扣5分。",
        "SP-02": "针对密码错误给出恢复路径，用户确认解决。",
        "SP-03": "用户确认问题已解决。",
        "SP-04": "账户登录问题与账户安全、登录异常标签语义一致。",
        "SP-05": "客服明确致谢并礼貌送别。",
        "PS-01": "客服明确引导立即重置密码，用户确认恢复，无适用扣分。",
        "PS-02": "针对安全问题主动提供第一步保护操作。",
        "PS-03": "原始规则规定默认满分。",
        "CM-01": "使用您、请等礼貌表达，无责备或推卸。",
        "CM-02": "表达通顺，未出现重复标点或负面表情。",
        "CM-03": "人工接入后30秒内回复，符合90秒上限。",
        "CM-04": "两次用户消息均在300秒内得到回复。",
        "CM-05": "未出现人工转接行为。",
    }
    items = []
    for spec in context.rubric["items"]:
        item_id = spec["id"]
        message_id = {"SP-03": "m004", "SP-04": "m002", "SP-05": "m005"}.get(item_id, "m003")
        message = next(m for m in context.conversation.messages if m.message_id == message_id)
        score = 0 if item_id == "SP-01" else spec["max_score"]
        rule_ids = [item_id]
        if item_id in ("PS-01", "PS-02"):
            rule_ids.append(
                next(
                    rule.rule_id
                    for rule in context.professional_rules.rules
                    if rule.item_id == item_id
                )
            )
        items.append(
            {
                "item_id": item_id,
                "score": f"{score}/{spec['max_score']}",
                "reason": reasons[item_id],
                "rule_ids": rule_ids,
                "evidence": [{"message_id": message_id, "quote": message.content}],
            }
        )
    return {"dimension": context.dimension, "items": items}
