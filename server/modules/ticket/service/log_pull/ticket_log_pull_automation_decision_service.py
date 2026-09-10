"""自动化日志拉取同参数决策矩阵服务。

解决外部工单重复同步导致同参数拉取记录反复创建的问题：
自动化链路在创建拉取前不再只找"成功"记录，而是查看同参数最新一条记录的状态，
按决策矩阵决定创建新拉取、等待进行中记录、复用成功记录或对失败记录静默跳过。

决策规则（最新一条同参数记录的状态决定）：
- 不存在 / cancelled：创建新拉取记录，按新记录快照走后续 AI 与通知；
- 进行中（created/submitting/polling/downloading/processing）：不创建，等待完成；
  本次场景要求 AI 且该记录快照缺 autoAiEnabled 时，只补缺失键合并 AI 配置；
- success：不创建，复用该记录；按该记录已有 AI 任务决定是否触发自动 AI；
- failed / exception：不创建、不触发 AI、不发 IM 通知，仅写内部留痕。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.do.ticket_do import TicketEvent
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.enums.ticket_enums import (
    TicketAiAnalysisStatus,
    TicketEventType,
    TicketLogPullStatus,
)
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from utils.log_util import logger


@dataclass
class AutoLogPullDecision:
    """自动化日志拉取决策结果。

    action 含义：
    - create：允许创建新拉取记录；
    - wait：同参数记录正在拉取中，不创建，等待其完成后由既有链路驱动 AI；
    - reuse：复用同参数成功记录，按 analyze_existing 决定是否触发 AI；
    - skip_failed：同参数最新记录拉取失败，静默跳过（不创建、不 AI、不通知）。
    """

    action: str
    reason: str = ""
    record_id: int | None = None
    record_status: str | None = None
    # reuse 分支专用：是否对复用记录触发自动 AI 分析
    analyze_existing: bool = False
    # skip_failed / wait 分支留痕详情，写入工单事件与链路日志
    detail: dict[str, Any] = field(default_factory=dict)


class TicketLogPullAutomationDecisionService:
    """自动化日志拉取同参数决策服务，供同步自动化链路在创建拉取前调用。"""

    @classmethod
    def decide(
        cls,
        db: Session,
        ticket_id: int,
        payload,
        *,
        auto_ai_enabled: bool,
    ) -> AutoLogPullDecision:
        """
        按同参数最新记录状态输出自动化拉取决策。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param payload: 本次拉取创建模型（TicketLogPullCreateModel）
        :param auto_ai_enabled: 本次自动化场景是否要求自动 AI 分析
        :return: 决策结果
        """
        target_signature = TicketLogPullService._build_pull_identity_from_payload(payload)
        candidates = TicketLogPullDao.list_recent_records_by_pull_identity(
            db,
            ticket_id=ticket_id,
            environment=payload.environment,
            vendor_id=int(payload.vendor_id),
            store_id=str(payload.store_id or "").strip(),
            pos_no=int(payload.pos_no),
            command_data_type=int(payload.command_data_type or 1),
        )
        latest = None
        for record in candidates:
            # 签名比对忽略通知与 AI 元数据，只比较影响拉取行为的参数
            if TicketLogPullService._build_pull_identity_from_record(record) == target_signature:
                latest = record
                break
        if latest is None:
            return AutoLogPullDecision(action="create", reason="不存在相同拉取参数的记录")

        status = str(latest.status or "").strip()
        detail = {
            "existingRecordId": str(latest.id),
            "existingStatus": status,
            "existingCreateTime": latest.create_time.isoformat(sep=" ") if latest.create_time else None,
        }
        if status in TicketLogPullService.ACTIVE_STATUSES:
            merged = cls._merge_auto_ai_into_active_record(db, latest, auto_ai_enabled=auto_ai_enabled)
            merge_note = "，已补充自动AI配置" if merged else ""
            return AutoLogPullDecision(
                action="wait",
                reason=f"相同拉取参数记录[{latest.id}]正在拉取中（{status}），等待完成后由既有链路处理{merge_note}",
                record_id=latest.id,
                record_status=status,
                detail=detail,
            )
        if status == TicketLogPullStatus.SUCCESS.value:
            analyze_existing = cls._should_analyze_existing_record(db, latest, auto_ai_enabled=auto_ai_enabled)
            return AutoLogPullDecision(
                action="reuse",
                reason=f"复用相同拉取参数的成功记录[{latest.id}]",
                record_id=latest.id,
                record_status=status,
                analyze_existing=analyze_existing,
                detail=detail,
            )
        if status in {TicketLogPullStatus.FAILED.value, TicketLogPullStatus.EXCEPTION.value}:
            return AutoLogPullDecision(
                action="skip_failed",
                reason=(
                    f"相同拉取参数最新记录[{latest.id}]已失败（{status}），本次不再重复创建拉取，"
                    f"也不触发AI分析与通知"
                ),
                record_id=latest.id,
                record_status=status,
                detail={**detail, "errorMessage": (latest.error_message or "")[:500]},
            )
        # cancelled 及其它未知终态：视为无有效记录，允许重新创建
        return AutoLogPullDecision(
            action="create",
            reason=f"相同拉取参数记录[{latest.id}]状态为{status}，允许重新创建拉取",
            record_id=latest.id,
            record_status=status,
            detail=detail,
        )

    @classmethod
    def _merge_auto_ai_into_active_record(
        cls, db: Session, record: TicketLogPullRecord, *, auto_ai_enabled: bool
    ) -> bool:
        """
        对进行中记录补充缺失的自动 AI 配置（只补缺失键，不覆盖已有值）。

        背景：进行中记录可能是此前人工创建或未勾选自动AI的任务，本次自动化场景要求 AI 时
        将 Agent/Provider/AI条件合并进 _automation 快照，拉取完成后既有链路即可按配置触发。

        :param db: 数据库会话
        :param record: 进行中的拉取记录
        :param auto_ai_enabled: 本次自动化场景是否要求自动 AI
        :return: 是否发生了合并写入
        """
        if not auto_ai_enabled:
            return False
        command_content = (
            dict(record.command_content)
            if isinstance(record.command_content, dict)
            else TicketLogPullService._json_loads(record.command_content, {})
        )
        if not isinstance(command_content, dict):
            command_content = {}
        automation = (
            dict(command_content.get("_automation"))
            if isinstance(command_content.get("_automation"), dict)
            else {}
        )
        if automation.get("autoAiEnabled"):
            return False
        automation["autoAiEnabled"] = True
        command_content["_automation"] = automation
        now = datetime.now()
        TicketLogPullDao.update_record(
            db,
            record.id,
            {
                "command_content": command_content,
                "update_by": "system",
                "update_time": now,
            },
        )
        db.commit()
        logger.info(
            f"自动化决策：进行中拉取记录[{record.id}]已补充自动AI配置，等待拉取完成后触发分析"
        )
        return True

    @classmethod
    def _should_analyze_existing_record(
        cls, db: Session, record: TicketLogPullRecord, *, auto_ai_enabled: bool
    ) -> bool:
        """
        判断复用的成功记录是否需要触发自动 AI 分析。

        规则：
        - 本次场景未启用自动 AI：不分析；
        - 记录已有 AI 任务：
          - 最新任务成功或执行中：不重复分析；
          - 最新任务失败/取消等终态：不重复分析（与拉取失败同策略，避免重复消耗与打扰）；
        - 记录无任何 AI 任务：需要分析（典型场景：复用人工创建且未勾选自动AI的成功记录）。

        :param db: 数据库会话
        :param record: 复用的成功拉取记录
        :param auto_ai_enabled: 本次自动化场景是否要求自动 AI
        :return: 是否触发自动 AI
        """
        if not auto_ai_enabled:
            return False
        latest_task = TicketAiDao.get_latest_task_by_log_pull_record_id(db, record.id)
        if not latest_task:
            return True
        latest_status = str(latest_task.status or "").strip()
        if latest_status in {
            TicketAiAnalysisStatus.SUCCESS.value,
            TicketAiAnalysisStatus.CREATED.value,
            TicketAiAnalysisStatus.RUNNING.value,
        }:
            logger.info(
                f"自动化决策：成功记录[{record.id}]已有AI任务 task_id={latest_task.task_id} "
                f"状态={latest_status}，跳过重复分析"
            )
            return False
        logger.info(
            f"自动化决策：成功记录[{record.id}]最新AI任务状态={latest_status}，按失败不重试策略跳过分析"
        )
        return False

    @classmethod
    def record_skip_event(
        cls,
        db: Session,
        *,
        ticket_id: int,
        decision: AutoLogPullDecision,
        sync_scene: str,
        operator_name: str = "system",
    ) -> None:
        """
        静默跳过（wait / skip_failed）时写内部留痕：工单事件 + 链路步骤日志。

        不发送 IM 通知——失败记录此前已通知过，进行中记录完成后会由既有链路通知。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param decision: 决策结果
        :param sync_scene: 触发同步场景
        :param operator_name: 操作人名称
        :return: 无
        """
        if decision.action not in {"wait", "skip_failed"} or not ticket_id:
            return
        event_payload = {
            "recordId": decision.record_id,
            "recordStatus": decision.record_status,
            "action": decision.action,
            "scene": sync_scene,
            "reason": decision.reason,
            **(decision.detail or {}),
        }
        try:
            db.add(
                TicketEvent(
                    ticket_id=ticket_id,
                    event_type=TicketEventType.LOG_ANALYSIS.value,
                    operator_id=None,
                    operator_name=operator_name,
                    content="自动日志拉取按同参数决策跳过",
                    event_data=event_payload,
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"自动化决策跳过留痕写入工单事件失败: ticket_id={ticket_id}, error={exc}")
            return
        logger.info(
            f"自动化决策留痕: ticket_id={ticket_id}, action={decision.action}, "
            f"record_id={decision.record_id}, reason={decision.reason}"
        )
