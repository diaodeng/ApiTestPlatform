from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_sync_process_state_do import TicketSyncProcessState

# 群推送处理锁超时秒数：超时视为残留锁可被抢占（对齐原 extra_data 实现的 GROUP_PUSH_LOCK_TIMEOUT_SECONDS）。
GROUP_PUSH_LOCK_TIMEOUT_SECONDS = 300


class TicketSyncProcessStateDao:
    """
    工单同步过程状态数据访问层（发布域 + 群推送执行域，一工单一行）。

    服务层切换（阶段 2b）前的存储地基：提供行级锁读写与按域更新能力，
    按域拆分更新方法（update_publish_state / update_push_fields），
    严禁全量字段覆盖式保存，防止宽表退化为新的"整包读改写"。
    """

    @classmethod
    def get_state(cls, db: Session, ticket_id: int, *, for_update: bool = False) -> TicketSyncProcessState | None:
        """
        查询工单过程状态行；行不存在返回 None（视为默认态：可发布、未推送过）。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param for_update: 是否加行级锁（群推送去重/状态收敛并发场景使用）
        :return: 状态 ORM 对象或 None
        """
        if not ticket_id:
            return None
        query = db.query(TicketSyncProcessState).filter(TicketSyncProcessState.ticket_id == ticket_id)
        if for_update:
            query = query.with_for_update()
        return query.first()

    @classmethod
    def ensure_state(cls, db: Session, ticket_id: int, update_by: str = "system") -> TicketSyncProcessState:
        """
        确保状态行存在（不存在则按默认值创建），返回行对象；由调用方事务边界提交。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param update_by: 创建人
        :return: 状态 ORM 对象
        """
        state = cls.get_state(db, ticket_id, for_update=True)
        if state is not None:
            return state
        state = TicketSyncProcessState(ticket_id=ticket_id, update_by=update_by)
        db.add(state)
        db.flush()
        return state

    @classmethod
    def update_publish_state(
        cls,
        db: Session,
        ticket_id: int,
        *,
        ready: bool,
        status: str,
        reason: str,
        ai_task_status: str | None = None,
        update_by: str = "system",
    ) -> TicketSyncProcessState:
        """
        更新发布域列（publish_ready/publish_status/publish_reason/publish_updated_at/ai_task_status）。
        仅更新发布域列，不触碰群推送执行域；行不存在时创建。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param ready: 是否允许对外发布
        :param status: 发布状态编码（ready/processing_ai）
        :param reason: 状态说明
        :param ai_task_status: AI任务状态；None 表示保持原值不变
        :param update_by: 更新人
        :return: 更新后的状态行
        """
        state = cls.ensure_state(db, ticket_id, update_by=update_by)
        state.publish_ready = bool(ready)
        state.publish_status = str(status or "").strip() or "ready"
        state.publish_reason = str(reason or "").strip()[:255]
        state.publish_updated_at = datetime.now()
        if ai_task_status is not None:
            state.ai_task_status = str(ai_task_status or "").strip()[:16]
        state.update_by = str(update_by or "system")[:100]
        return state

    @classmethod
    def update_push_fields(
        cls,
        db: Session,
        ticket_id: int,
        fields: dict[str, Any],
        *,
        update_by: str = "system",
    ) -> TicketSyncProcessState:
        """
        更新群推送执行域列（白名单校验：只接受 push_ 前缀的合法列名）。
        供群推送链路按需更新 sent_once/processing 锁等字段；行不存在时创建。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param fields: 待更新字段字典（键必须为 push_ 前缀的 ORM 列名）
        :param update_by: 更新人
        :return: 更新后的状态行
        :raises ValueError: 字段名不在群推送域白名单内
        """
        allowed_fields = {
            "push_sent_once",
            "push_sent_at",
            "push_scene",
            "push_revision",
            "push_processing",
            "push_processing_at",
            "push_processing_scene",
            "push_processing_revision",
        }
        unknown = set(fields or {}) - allowed_fields
        if unknown:
            raise ValueError(f"非法群推送状态字段: {sorted(unknown)}")
        state = cls.ensure_state(db, ticket_id, update_by=update_by)
        for key, value in (fields or {}).items():
            setattr(state, key, value)
        state.update_by = str(update_by or "system")[:100]
        return state

    @classmethod
    def acquire_push_processing_lock(
        cls,
        db: Session,
        ticket_id: int,
        *,
        scene: str,
        revision: int,
        timeout_seconds: int = GROUP_PUSH_LOCK_TIMEOUT_SECONDS,
        update_by: str = "system",
    ) -> tuple[bool, str, TicketSyncProcessState | None]:
        """
        抢占群推送处理锁（行级锁内判定：已发送过/锁被占用未超时均失败）。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param scene: 触发场景
        :param revision: 当前修订号
        :param timeout_seconds: 残留锁超时秒数
        :param update_by: 更新人
        :return: (是否抢到, 失败原因, 状态行)
        """
        state = cls.ensure_state(db, ticket_id, update_by=update_by)
        if bool(state.push_sent_once):
            return False, "already_sent", state
        if bool(state.push_processing):
            locked_at = state.push_processing_at
            if locked_at and (datetime.now() - locked_at).total_seconds() < timeout_seconds:
                return False, "group_push_processing", state
        state.push_processing = True
        state.push_processing_at = datetime.now()
        state.push_processing_scene = str(scene or "")[:32]
        state.push_processing_revision = int(revision or 0)
        return True, "acquired", state

    @classmethod
    def release_push_processing_lock(
        cls,
        db: Session,
        ticket_id: int,
        *,
        update_by: str = "system",
    ) -> TicketSyncProcessState | None:
        """
        释放群推送处理锁（幂等：未持锁时无操作）。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param update_by: 更新人
        :return: 状态行或 None（行不存在）
        """
        state = cls.get_state(db, ticket_id)
        if state is None or not bool(state.push_processing):
            return state
        state.push_processing = False
        state.push_processing_at = None
        state.push_processing_scene = ""
        state.push_processing_revision = 0
        state.update_by = str(update_by or "system")[:100]
        return state

    @classmethod
    def mark_push_sent_once(
        cls,
        db: Session,
        ticket_id: int,
        *,
        scene: str,
        revision: int,
        update_by: str = "system",
    ) -> TicketSyncProcessState:
        """
        标记工单信息群消息已成功发送（工单级仅一次），同时清掉处理锁。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param scene: 触发场景
        :param revision: 当前修订号
        :param update_by: 更新人
        :return: 更新后的状态行
        """
        state = cls.ensure_state(db, ticket_id, update_by=update_by)
        state.push_sent_once = True
        state.push_sent_at = datetime.now()
        state.push_scene = str(scene or "")[:32]
        state.push_revision = int(revision or 0)
        state.push_processing = False
        state.push_processing_at = None
        state.push_processing_scene = ""
        state.push_processing_revision = 0
        state.update_by = str(update_by or "system")[:100]
        return state

    @classmethod
    def list_states_for_pull(cls, db: Session, ticket_ids: list[int]) -> dict[int, TicketSyncProcessState]:
        """
        批量查询工单过程状态（delivery 拉取链路组装 syncSummary 使用）。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: ticket_id -> 状态行映射（无行的工单不在映射中，调用方按默认态处理）
        """
        normalized = [int(item) for item in (ticket_ids or []) if item]
        if not normalized:
            return {}
        rows = db.query(TicketSyncProcessState).filter(
            TicketSyncProcessState.ticket_id.in_(normalized)
        ).all()
        return {int(row.ticket_id): row for row in rows}
