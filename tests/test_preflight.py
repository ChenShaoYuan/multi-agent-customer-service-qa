from customer_service_qa.adapters import normalize_input
from customer_service_qa.preflight import run_preflight


def test_missing_timestamps_are_not_scored_as_violations() -> None:
    conversation = normalize_input(
        {
            "ticketId": 1,
            "tag": "账户-登录异常",
            "parentTag": "账户安全",
            "comments": "无法登录\n您好，请提供报错信息\n密码错误\n感谢反馈，祝您生活愉快",
        }
    )

    report = run_preflight(conversation)

    assert report.input_valid
    assert not report.timing_available
    assert report.response_time_violations == []
    assert report.greeting.present is True
    assert report.closing.present is True


def test_response_and_first_response_timing_are_calculated() -> None:
    conversation = normalize_input(
        {
            "ticket_id": "T-2",
            "tag": "账户-登录异常",
            "parent_tag": "账户安全",
            "messages": [
                {
                    "role": "system",
                    "content": "正在连接客服",
                    "timestamp": "2026-09-22T10:00:00+08:00",
                },
                {
                    "role": "end-user",
                    "content": "无法登录",
                    "timestamp": "2026-09-22T10:00:10+08:00",
                },
                {
                    "role": "agent",
                    "content": "您好",
                    "timestamp": "2026-09-22T10:06:00+08:00",
                },
            ],
        }
    )

    report = run_preflight(conversation)

    assert report.timing_available
    assert report.first_response_evaluable
    assert report.first_response_seconds == 360
    assert report.first_response_violation is True
    assert report.response_time_violations[0].elapsed_seconds == 350


def test_keyword_hit_is_only_a_hint_and_sensitive_data_is_masked() -> None:
    conversation = normalize_input(
        {
            "ticket_id": "T-3",
            "tag": "账户-登录异常",
            "parent_tag": "账户安全",
            "messages": [
                {"role": "end-user", "content": "怎么处理"},
                {"role": "agent", "content": "不归我们管，手机号是13812345678"},
            ],
        }
    )

    report = run_preflight(conversation)

    assert report.redline_keyword_hits[0].rule_id == "CR-01"
    assert report.input_valid
    assert report.sensitive_data_hits[0].masked_value != "13812345678"


def test_unknown_parent_tag_is_reported() -> None:
    conversation = normalize_input(
        {
            "ticket_id": "T-4",
            "tag": "未知-问题",
            "parent_tag": "未知分类",
            "messages": [
                {"role": "end-user", "content": "问题"},
                {"role": "agent", "content": "您好"},
            ],
        }
    )

    report = run_preflight(conversation)

    assert report.tag_warnings == ["unknown_parent_tag:未知分类"]


def test_repeated_reply_and_transfer_are_detected() -> None:
    conversation = normalize_input(
        {
            "ticket_id": "T-5",
            "tag": "账户-登录异常",
            "parent_tag": "账户安全",
            "messages": [
                {"role": "end-user", "content": "问题"},
                {"role": "agent", "content": "请稍等"},
                {"role": "agent", "content": "请稍等"},
                {"role": "agent", "content": "现在为您转接至安全团队"},
            ],
        }
    )

    report = run_preflight(conversation)

    assert report.repeated_reply_message_ids == [["m002", "m003"]]
    assert report.transfer_events[0].message_id == "m004"
