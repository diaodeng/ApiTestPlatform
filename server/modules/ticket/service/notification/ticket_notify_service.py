from __future__ import annotations

from string import Template
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

    DEFAULT_TEMPLATE = (
        "${title}\n"
        "工单号：${ticket_no}\n"
        "工单标题：${ticket_title}\n"
        "商家：${merchant_name}\n"
        "门店：${store_name}\n"
        "阶段：${stage_label}\n"
        "状态：${status_label}\n"
        "原因：${reason}"
    )

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
        stage: str | None = None,
        template: str | None = None,
    ) -> str:
        """
        构造工单通知消息文本。

        :param title: 通知标题。
        :param ticket: 工单对象。
        :param status: 当前状态，如 success 或 failed。
        :param message: 简要说明。
        :param detail: 额外说明。
        :param stage: 自动化当前阶段。
        :param template: 可选消息模板。
        :return: 格式化文本。
        """
        variables = cls.build_template_variables(
            ticket=ticket,
            title=title,
            status=status,
            message=message,
            detail=detail,
            stage=stage,
        )
        message_template = str(template or "").strip() or cls.DEFAULT_TEMPLATE
        try:
            return Template(message_template).safe_substitute(variables)
        except ValueError as exc:
            logger.warning(f"工单通知模板格式不合法，已使用默认模板: error={exc}")
            return Template(cls.DEFAULT_TEMPLATE).safe_substitute(variables)

    @classmethod
    def build_template_variables(
        cls,
        *,
        ticket: Ticket | None,
        title: str,
        status: str,
        message: str,
        detail: str | None = None,
        stage: str | None = None,
    ) -> dict[str, str]:
        """
        构造自动化结果通知模板变量。

        :param ticket: 工单 ORM 实体。
        :param title: 通知标题。
        :param status: 当前结果状态。
        :param message: 简要说明。
        :param detail: 详情或异常原因。
        :param stage: 自动化阶段编码。
        :return: 可供消息模板替换的变量字典。
        """
        extra_data = ticket.extra_data if ticket and isinstance(ticket.extra_data, dict) else {}
        log_hints = extra_data.get("log_pull_hints") if isinstance(extra_data.get("log_pull_hints"), dict) else {}
        raw_payload = extra_data.get("raw_payload") if isinstance(extra_data.get("raw_payload"), dict) else {}
        store_name = next(
            (
                str(value).strip()
                for value in (
                    log_hints.get("storeName"),
                    log_hints.get("store_name"),
                    raw_payload.get("storeName"),
                    raw_payload.get("store_name"),
                    raw_payload.get("ticketStore"),
                    raw_payload.get("storeInfo"),
                    log_hints.get("storeId"),
                    log_hints.get("sourceStoreCode"),
                )
                if str(value or "").strip()
            ),
            "-",
        )
        status_key = "success" if str(status).lower() == "success" else "failed"
        stage_key = str(stage or "").strip().lower()
        stage_labels = {
            "log_pull": "日志拉取",
            "auto_ai_analysis": "自动 AI 分析",
            "ai_analysis": "AI 分析",
            "automation": "同步后自动化",
        }
        return {
            "title": str(title or "-"),
            "ticket_no": str(getattr(ticket, "ticket_no", "") or "-"),
            "ticket_title": str(getattr(ticket, "title", "") or "-"),
            "merchant_name": str(getattr(ticket, "merchant_name", "") or "-"),
            "store_name": store_name,
            "ticket_url": str(getattr(ticket, "ticket_url", "") or "-"),
            "stage": stage_key or "-",
            "stage_label": stage_labels.get(stage_key, stage_key or "自动化"),
            "status": str(status or "-"),
            "status_label": "成功" if status_key == "success" else "失败",
            "message": str(message or "-"),
            "detail": str(detail or "-"),
            "reason": str(detail or message or "-"),
        }

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
        stage: str | None = None,
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
        :param stage: 自动化当前阶段，用于模板变量。
        :return: 无。
        """
        notify_config = (
            notify_config
            if isinstance(notify_config, dict) and notify_config
            else cls._extract_notify_config(ticket)
        )
        push_ids = notify_config.get("pushIds") or notify_config.get("push_ids") or []
        if not push_ids:
            logger.info(
                f"工单通知跳过: ticket_no={getattr(ticket, 'ticket_no', '-')}, "
                f"stage={stage or '-'}, reason=未配置推送渠道"
            )
            return
        if "enabled" in notify_config and not bool(notify_config.get("enabled")):
            logger.info(
                f"工单通知跳过: ticket_no={getattr(ticket, 'ticket_no', '-')}, "
                f"stage={stage or '-'}, reason=通知开关未启用"
            )
            return
        allow_push = notify_config.get("allowPush")
        if allow_push in (0, "0", False):
            logger.info(
                f"工单通知跳过: ticket_no={getattr(ticket, 'ticket_no', '-')}, "
                f"stage={stage or '-'}, reason=推送权限未开启"
            )
            return
        status_key = "success" if str(status).lower() == "success" else "failed"
        status_config = notify_config.get(status_key)
        if isinstance(status_config, dict) and not bool(status_config.get("push")):
            logger.info(
                f"工单通知跳过: ticket_no={getattr(ticket, 'ticket_no', '-')}, "
                f"stage={stage or '-'}, status={status_key}, reason=结果通知开关未启用"
            )
            return
        content = cls.build_message(
            title=title,
            ticket=ticket,
            status=status,
            message=message,
            detail=detail,
            stage=stage,
            template=notify_config.get("messageTemplate") or notify_config.get("message_template"),
        )
        logger.info(
            f"工单通知开始投递: ticket_no={getattr(ticket, 'ticket_no', '-')}, "
            f"stage={stage or '-'}, status={status_key}, push_count={len(push_ids)}"
        )
        for push_id in push_ids:
            try:
                detail_row = PushDao.get(db, int(push_id))
                if not detail_row:
                    continue
                MessageHandler(PushModel.model_validate(detail_row), {}).push(content=content)
            except Exception as exc:
                logger.warning(f"发送工单通知失败 | push_id={push_id}, error={exc}")
