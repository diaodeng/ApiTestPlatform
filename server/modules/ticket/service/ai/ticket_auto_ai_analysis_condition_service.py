"""工单自动 AI 分析条件服务。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus


class TicketAutoAiAnalysisConditionService:
    """统一检查自动 AI 分析的历史任务和内部工单状态条件。"""

    @classmethod
    def resolve_condition(cls, command_content: dict[str, Any]) -> dict[str, Any]:
        """
        读取并归一化自动 AI 条件快照。
        :param command_content: 日志拉取记录或自动化运行时配置
        :return: 自动 AI 条件
        """
        automation = command_content.get("_automation") if isinstance(command_content.get("_automation"), dict) else {}
        raw_condition = automation.get("autoAiAnalysisCondition") or command_content.get("autoAiAnalysisCondition")
        raw_condition = raw_condition if isinstance(raw_condition, dict) else {}
        analysis_mode = str(raw_condition.get("analysisMode") or "always").strip()
        if analysis_mode not in {"always", "not_successful"}:
            analysis_mode = "always"
        status_codes: list[str] = []
        raw_status_codes = raw_condition.get("statusCodes")
        if isinstance(raw_status_codes, list):
            for item in raw_status_codes:
                status_code = str(item or "").strip()
                if status_code and status_code not in status_codes:
                    status_codes.append(status_code)
        return {
            "analysisMode": analysis_mode,
            "statusFilterEnabled": bool(raw_condition.get("statusFilterEnabled")),
            "statusCodes": status_codes,
        }

    @classmethod
    def check_conditions(
        cls, db: Session, ticket: Any, condition: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """
        检查自动 AI 分析的状态、历史任务和活动任务条件。
        :param db: 数据库会话
        :param ticket: 工单实体
        :param condition: 自动 AI 条件
        :return: 需要跳过时返回原因与详情，否则返回 None
        """
        ticket_status = str(getattr(ticket, "status", "") or "").strip()
        allowed_status_codes = condition.get("statusCodes") if isinstance(condition.get("statusCodes"), list) else []
        if condition.get("statusFilterEnabled") and (
            not ticket_status or ticket_status not in allowed_status_codes
        ):
            return (
                "工单状态不满足自动AI分析条件",
                {
                    "ticketStatus": ticket_status,
                    "allowedStatusCodes": allowed_status_codes,
                },
            )

        if condition.get("analysisMode") == "not_successful":
            successful_task = TicketAiDao.get_last_successful_task_by_ticket(db, ticket.ticket_id)
            if successful_task:
                return (
                    "工单已有成功的AI分析记录",
                    {"analysisMode": "not_successful", "successfulTaskId": getattr(successful_task, "task_id", None)},
                )

        latest_task = TicketAiDao.get_latest_task_by_ticket_id(db, ticket.ticket_id)
        active_statuses = {TicketAiAnalysisStatus.CREATED.value, TicketAiAnalysisStatus.RUNNING.value}
        latest_status = str(getattr(latest_task, "status", "") or "").strip() if latest_task else ""
        if latest_task and latest_status in active_statuses:
            return (
                "工单已有正在执行的AI分析任务",
                {
                    "latestTaskId": getattr(latest_task, "task_id", None),
                    "latestTaskStatus": latest_status,
                },
            )
        return None
