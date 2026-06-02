from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.vo.push_vo import PushModel
from modules.ticket.entity.do.ticket_do import Ticket
from utils.log_util import logger
from utils.message_util import MessageHandler


class TicketNotifyService:
    """
    工单通知服务，统一按工单自动化配置发送推送消息。
    """

    @classmethod
    def _extract_notify_config(cls, ticket: Ticket | None) -> dict[str, Any]:
        """
        提取工单自动化中的通知配置。

        :param ticket: 工单对象。
        :return: 通知配置字典。
        """
        if not ticket or not isinstance(ticket.extra_data, dict):
            return {}
        automation = ticket.extra_data.get("ticket_automation")
        if not isinstance(automation, dict):
            return {}
        notify_config = automation.get("notifyConfig") or automation.get("notify_config")
        if not isinstance(notify_config, dict):
            log_pull_config = automation.get("logPullConfig") or automation.get("log_pull_config")
            if isinstance(log_pull_config, dict):
                notify_config = log_pull_config.get("notifyConfig") or log_pull_config.get("notify_config")
        return notify_config if isinstance(notify_config, dict) else {}

    @classmethod
    def build_message(
        cls,
        *,
        title: str,
        ticket: Ticket | None,
        status: str,
        message: str,
        detail: str | None = None,
    ) -> str:
        """
        构造工单通知消息文本。

        :param title: 通知标题。
        :param ticket: 工单对象。
        :param status: 当前状态，如 success 或 failed。
        :param message: 简要说明。
        :param detail: 额外说明。
        :return: 格式化文本。
        """
        ticket_no = getattr(ticket, "ticket_no", "") or "-"
        ticket_title = getattr(ticket, "title", "") or "-"
        project_name = getattr(ticket, "merchant_name", "") or "-"
        lines = [
            f"{title}",
            f"工单：{ticket_no} / {ticket_title}",
            f"项目：{project_name}",
            f"状态：{status}",
            f"说明：{message}",
        ]
        if detail:
            lines.append(f"详情：{detail}")
        return "\n".join(lines)

    @classmethod
    def send_ticket_notification(
        cls,
        db: Session,
        ticket: Ticket | None,
        *,
        title: str,
        status: str,
        message: str,
        detail: str | None = None,
        notify_config: dict[str, Any] | None = None,
    ) -> None:
        """
        按工单自动化配置发送推送通知。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param title: 通知标题。
        :param status: 当前状态，如 success 或 failed。
        :param message: 简要说明。
        :param detail: 额外说明。
        :param notify_config: 覆盖用的通知配置，未传或为空时回退到工单自动化配置。
        :return: 无。
        """
        notify_config = (
            notify_config
            if isinstance(notify_config, dict) and notify_config
            else cls._extract_notify_config(ticket)
        )
        push_ids = notify_config.get("pushIds") or notify_config.get("push_ids") or []
        if not push_ids:
            return
        allow_push = notify_config.get("allowPush")
        if allow_push in (0, "0", False):
            return
        status_key = "success" if str(status).lower() == "success" else "failed"
        status_config = notify_config.get(status_key)
        if isinstance(status_config, dict) and not bool(status_config.get("push")):
            return
        content = cls.build_message(
            title=title,
            ticket=ticket,
            status=status,
            message=message,
            detail=detail,
        )
        for push_id in push_ids:
            try:
                detail_row = PushDao.get(db, int(push_id))
                if not detail_row:
                    continue
                MessageHandler(PushModel.model_validate(detail_row), {}).push(content=content)
            except Exception as exc:
                logger.warning(f"发送工单通知失败 | push_id={push_id}, error={exc}")
