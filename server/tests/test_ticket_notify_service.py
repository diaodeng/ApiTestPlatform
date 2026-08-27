from types import SimpleNamespace

from modules.ticket.service.notification.ticket_notify_service import TicketNotifyService


def test_build_message_replaces_automation_notification_variables():
    """自动化通知模板应替换工单、商家、门店和失败原因变量。"""
    ticket = SimpleNamespace(
        ticket_no="T-20260825-001",
        title="收银终端无法结账",
        merchant_name="示例商家",
        ticket_url="https://ticket.example.com/T-20260825-001",
        extra_data={"log_pull_hints": {"storeName": "上海徐汇店"}},
    )

    message = TicketNotifyService.build_message(
        ticket=ticket,
        title="工单自动化结果通知",
        status="failed",
        message="自动日志拉取已跳过",
        detail="缺少 POS 编号",
        stage="log_pull",
        template="${ticket_no}|${merchant_name}|${store_name}|${stage_label}|${status_label}|${reason}",
    )

    assert message == "T-20260825-001|示例商家|上海徐汇店|日志拉取|失败|缺少 POS 编号"


def test_build_message_uses_default_template_when_template_is_empty():
    """模板留空时应使用包含核心业务信息的默认通知内容。"""
    ticket = SimpleNamespace(
        ticket_no="T-20260825-002",
        title="日志下载失败",
        merchant_name="示例商家",
        ticket_url="",
        extra_data={"log_pull_hints": {"storeId": "10086"}},
    )

    message = TicketNotifyService.build_message(
        ticket=ticket,
        title="工单自动化结果通知",
        status="success",
        message="日志拉取已完成",
        stage="log_pull",
    )

    assert "工单号：T-20260825-002" in message
    assert "门店：10086" in message
    assert "状态：成功" in message
