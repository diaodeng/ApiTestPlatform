"""工单自定义统计通知的文本和飞书卡片渲染服务。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from module_hrm.utils.parser import parse_string
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from utils.log_util import logger


class TicketStatisticsNotificationService:
    """将标准化统计结果渲染后交由统一通知通道投递。"""

    DEFAULT_TEMPLATE = (
        "【${profile_label}】\n"
        "统计范围：${start_time} ~ ${end_time}\n"
        "统计时间字段：${time_field_label}\n"
        "工单总数：${total_count}\n\n"
        "${group_summary}\n\n"
        "${top_tickets}\n"
        "生成时间：${now_time}"
    )

    @classmethod
    def send_result(
        cls,
        db: Session,
        *,
        notification: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """按方案通知配置发送实时统计结果。"""
        variables = cls.build_template_variables(result)
        content = cls.render_template(notification.get("messageTemplate"), variables)
        card = (
            cls.build_feishu_card(variables["profile_label"], content)
            if notification.get("messageFormat") == "feishu_card"
            else None
        )
        return TicketSyncNotifyService.send_configured_notification(
            db,
            config=notification,
            content=content,
            feishu_card=card,
        )

    @classmethod
    def build_template_variables(cls, result: dict[str, Any]) -> dict[str, Any]:
        """构造受控模板变量，不向模板暴露 ORM 对象。"""
        groups = result.get("groups") if isinstance(result.get("groups"), list) else []
        group_summary = "\n".join(
            f"- {str(item.get('label') or item.get('code') or '未分组')}：{int(item.get('count') or 0)}"
            for item in groups
        ) or "- 无命中数据"
        top_tickets = result.get("topTickets") if isinstance(result.get("topTickets"), list) else []
        top_ticket_text = ""
        if top_tickets:
            rows = ["工单明细："]
            for index, item in enumerate(top_tickets, start=1):
                ticket_no = str(item.get("ticketNo") or "-")
                title = str(item.get("title") or "-")
                ticket_url = str(item.get("ticketUrl") or "").strip()
                rows.append(f"{index}. {ticket_no} / {title}" + (f"\n{ticket_url}" if ticket_url else ""))
            top_ticket_text = "\n".join(rows)
        return {
            "profile_code": result.get("profileCode"),
            "profile_label": result.get("profileLabel"),
            "start_time": result.get("startTime"),
            "end_time": result.get("endTime"),
            "time_field": result.get("timeField"),
            "time_field_label": result.get("timeFieldLabel"),
            "total_count": result.get("totalCount"),
            "unmatched_count": result.get("unmatchedCount"),
            "group_summary": group_summary,
            "top_tickets": top_ticket_text,
            "now_time": result.get("executedAt"),
        }

    @classmethod
    def render_template(cls, template: Any, variables: dict[str, Any]) -> str:
        """渲染文本模板，模板异常时回退默认模板。"""
        template_text = str(template or "").strip() or cls.DEFAULT_TEMPLATE
        try:
            return str(parse_string(template_text, variables, {}, False)).strip()
        except Exception as exc:
            logger.warning(f"自定义统计通知模板渲染失败，已使用默认模板: error={exc}")
            return str(parse_string(cls.DEFAULT_TEMPLATE, variables, {}, False)).strip()

    @staticmethod
    def build_feishu_card(title: Any, content: str) -> dict[str, Any]:
        """构造只含受控文本内容的飞书交互卡片。"""
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": str(title or "工单统计")}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
        }
