"""
工单 AI 分析连接中断恢复扫描服务。

职责单一：周期扫描 pending_recovery（连接中断等待补交）状态的 AI 分析任务，
- Agent 重连补交的结果已写入 Redis 结果缓存时，重新排队任务走迟到结果写回（不重复消耗 token）；
- 超过恢复期限（任务上下文 pendingRecoveryDeadline）仍无补交结果时置为失败并发送失败通知。

断连瞬间的 pending_recovery 状态写入由 TicketAiAnalysisService._enter_pending_recovery 完成，
本服务只负责后续的自动写回与超期兜底，不实现其他业务逻辑。
"""

from datetime import datetime

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.do.ticket_do import TicketAiAnalysisTask
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.notification.ticket_notify_service import TicketNotifyService
from utils.log_util import logger


class TicketAiRecoveryService:
    """
    工单 AI 分析连接中断恢复扫描服务。
    """

    # 任务上下文中恢复期限的键名，与 TicketAiAnalysisService._enter_pending_recovery 写入口径一致
    RECOVERY_DEADLINE_CONTEXT_KEY = "pendingRecoveryDeadline"

    @classmethod
    def scan_pending_recovery_tasks(cls, db: Session) -> dict:
        """
        扫描所有 pending_recovery 任务并推进恢复流程。

        :param db: 数据库会话
        :return: 扫描摘要字典（scanned/recovered/expired/waiting/failed）
        """
        tasks = TicketAiDao.list_recoverable_tasks(db, [TicketAiAnalysisStatus.PENDING_RECOVERY.value])
        summary: dict = {"scanned": len(tasks), "recovered": 0, "expired": 0, "waiting": 0, "failed": 0}
        now = datetime.now()
        for task in tasks:
            try:
                # 重读最新状态防并发：扫描期间任务可能已被其他流程处理（取消/写回）
                fresh_task = TicketAiDao.get_task_by_id(db, task.task_id)
                if not fresh_task or fresh_task.status != TicketAiAnalysisStatus.PENDING_RECOVERY.value:
                    continue
                cls._process_one_task(db, fresh_task, now, summary)
            except Exception as exc:
                summary["failed"] += 1
                db.rollback()
                logger.exception(
                    f"AI分析恢复扫描处理任务异常 | task_id={getattr(task, 'task_id', None)}, error={exc}"
                )
        return summary

    @classmethod
    def _process_one_task(cls, db: Session, task: TicketAiAnalysisTask, now: datetime, summary: dict) -> None:
        """
        处理单个恢复等待中的任务：补交命中则重新排队，超期则置败，否则继续等待。

        :param db: 数据库会话
        :param task: AI 分析任务（全量加载）
        :param now: 当前时间
        :param summary: 扫描摘要字典（原地累加）
        :return: 无
        """
        task_id = task.task_id
        request_id = TicketAiAnalysisService._resolve_task_last_request_id(task)
        if request_id and TicketAiAnalysisService._peek_agent_result_cache(request_id):
            # 补交结果已就位：重新排队，执行入口命中迟到结果缓存直接写回成功
            TicketAiAnalysisService.queue_task(task_id)
            summary["recovered"] += 1
            logger.info(f"AI分析任务[{task_id}] 检测到补交结果，重新排队恢复写回: request_id={request_id}")
            return

        deadline = cls._resolve_recovery_deadline(task)
        if deadline is not None and now > deadline:
            cls._mark_recovery_expired(db, task)
            summary["expired"] += 1
            return
        # 尚未超期且无补交结果：继续等待 Agent 重连
        summary["waiting"] += 1

    @classmethod
    def _resolve_recovery_deadline(cls, task: TicketAiAnalysisTask) -> datetime | None:
        """
        从任务上下文解析恢复截止时间。

        :param task: AI 分析任务
        :return: 恢复截止时间；上下文缺失或格式非法时返回 None（视为无限等待，仅人工介入）
        """
        context = task.analysis_context if isinstance(task.analysis_context, dict) else {}
        deadline_text = str(context.get(cls.RECOVERY_DEADLINE_CONTEXT_KEY) or "").strip()
        if not deadline_text:
            return None
        try:
            return datetime.fromisoformat(deadline_text)
        except Exception as exc:
            logger.warning(
                f"AI分析任务[{task.task_id}] 恢复期限格式非法，按无期限处理: value={deadline_text}, error={exc}"
            )
            return None

    @classmethod
    def _mark_recovery_expired(cls, db: Session, task: TicketAiAnalysisTask) -> None:
        """
        恢复超期置败：任务置 failed、审计置 failed、回写发布状态并发送失败通知。

        :param db: 数据库会话
        :param task: AI 分析任务
        :return: 无
        """
        task_id = task.task_id
        failure_message = "Agent 未在恢复期限内补交分析结果，任务已标记失败，请手动重试"
        TicketAiAnalysisService._log_task_step(task_id, "FAIL", "恢复等待超时", error=failure_message)
        TicketAiAnalysisService._mark_task_status(
            db,
            task_id,
            status=TicketAiAnalysisStatus.FAILED.value,
            status_desc="恢复超时失败",
            error_code="AI_RECOVERY_DEADLINE_EXCEEDED",
            error_message=failure_message,
            finished_at=datetime.now(),
        )
        TicketAiAnalysisService._update_execution_record(
            db,
            getattr(task, "audit_execution_id", None),
            status="failed",
            error_code="AI_RECOVERY_DEADLINE_EXCEEDED",
            error_message=failure_message,
        )
        db.commit()
        ticket = TicketDao.get_ticket_by_id(db, task.ticket_id)
        if not ticket:
            logger.warning(f"AI分析任务[{task_id}] 恢复超时置败，但工单不存在: ticket_id={task.ticket_id}")
            return
        TicketAiAnalysisService._finalize_sync_publish_after_ai(
            db,
            ticket_id=ticket.ticket_id,
            status=TicketAiAnalysisStatus.FAILED.value,
            task_id=task_id,
            error_message=failure_message,
        )
        TicketNotifyService.send_ticket_notification(
            db,
            ticket,
            title="工单AI分析结果通知",
            status="failed",
            message="AI分析恢复超时失败",
            detail=f"task_id={task_id}, error={failure_message}",
            notify_config=cls._resolve_notify_config(db, task),
            stage="ai_analysis",
        )
        logger.warning(f"AI分析任务[{task_id}] 恢复等待超时，已置为失败: ticket_id={task.ticket_id}")

    @classmethod
    def _resolve_notify_config(cls, db: Session, task: TicketAiAnalysisTask) -> dict | None:
        """
        解析任务的通知配置快照：与主执行链路同口径，从来源日志拉取记录读取。

        :param db: 数据库会话
        :param task: AI 分析任务
        :return: 通知配置字典，无来源记录时返回 None
        """
        if not getattr(task, "source_log_pull_record_id", None):
            return None
        record = TicketLogPullDao.get_record_meta_by_id(db, int(task.source_log_pull_record_id))
        if record and isinstance(record.command_content, dict):
            return record.command_content.get("notifyConfig") or record.command_content.get("notify_config")
        return None
