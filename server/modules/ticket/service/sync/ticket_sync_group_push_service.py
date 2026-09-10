"""
工单群消息推送服务：发布状态管理、群推送去重与并发控制、自动/手动推送。
从 TicketSyncService 中提取。
"""
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.dao.ticket_ai_dao import TicketAiDao
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus
from modules.ticket.service.sync.ticket_automation_scope_service import TicketAutomationScopeService
from modules.ticket.service.sync.ticket_sync_condition_evaluator import evaluate_ticket_condition
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.log_util import logger


class TicketSyncGroupPushService:
    """工单群消息推送与发布状态管理。"""

    PUBLISH_STATUS_READY = "ready"
    PUBLISH_STATUS_PROCESSING_AI = "processing_ai"
    AI_PENDING_AUTOMATION_STATUSES = {"queued", "submitted", "running"}
    AI_PENDING_TASK_STATUSES = {
        TicketAiAnalysisStatus.CREATED.value,
        TicketAiAnalysisStatus.RUNNING.value,
    }
    GROUP_PUSH_LOCK_TIMEOUT_SECONDS = 300
    SOURCE_CODE = "external_sync"
    META_KEY = "external_sync"

    @classmethod
    def build_meta(cls, extra_data: dict[str, Any] | None) -> dict[str, Any]:
        source = extra_data if isinstance(extra_data, dict) else {}
        meta = source.get(cls.META_KEY) if isinstance(source.get(cls.META_KEY), dict) else {}
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        meta.setdefault("revision", 0)
        meta.setdefault("source", {})
        meta["sync_state"] = {
            "status": str(sync_state.get("status") or "pending"),
            "last_pulled_at": sync_state.get("last_pulled_at"),
            "last_consumer": sync_state.get("last_consumer"),
            "last_batch_id": sync_state.get("last_batch_id"),
            "consumers": sync_state.get("consumers") if isinstance(sync_state.get("consumers"), dict) else {},
            "automation": sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {},
            "publish_ready": bool(sync_state.get("publish_ready", True)),
            "publish_status": str(sync_state.get("publish_status") or cls.PUBLISH_STATUS_READY),
            "publish_reason": str(sync_state.get("publish_reason") or "").strip(),
            "publish_updated_at": sync_state.get("publish_updated_at"),
            "ai_task_status": str(sync_state.get("ai_task_status") or "").strip(),
            "group_push_sent_once": bool(sync_state.get("group_push_sent_once", False)),
            "group_push_sent_at": sync_state.get("group_push_sent_at"),
            "group_push_scene": sync_state.get("group_push_scene"),
            "group_push_revision": sync_state.get("group_push_revision"),
            "group_push_processing": bool(sync_state.get("group_push_processing", False)),
            "group_push_processing_at": sync_state.get("group_push_processing_at"),
            "group_push_processing_scene": sync_state.get("group_push_processing_scene"),
            "group_push_processing_revision": sync_state.get("group_push_processing_revision"),
            # 群消息话题锚点与回帖幂等记录必须随 build_meta 往返保留，
            # 否则外部同步更新等读改写 extra_data 的链路会把锚点静默擦除，
            # 导致 AI 终态回帖因"无话题锚点"被 skip（INC00001934853/R 案例）。
            "group_push_message_refs": sync_state.get("group_push_message_refs")
            if isinstance(sync_state.get("group_push_message_refs"), list)
            else [],
            "ai_result_reply_task_ids": sync_state.get("ai_result_reply_task_ids")
            if isinstance(sync_state.get("ai_result_reply_task_ids"), list)
            else [],
            # 最近一次入库同步场景，AI 终态回调据此还原真实触发场景。
            "sync_scene": str(sync_state.get("sync_scene") or "").strip(),
        }
        return meta

    @classmethod
    def attach_meta(cls, extra_data: dict[str, Any] | None, meta: dict[str, Any]) -> dict[str, Any]:
        payload = dict(extra_data or {})
        payload[cls.META_KEY] = meta
        return payload

    @classmethod
    def extract_sync_summary(cls, extra_data: Any) -> dict[str, Any] | None:
        if not isinstance(extra_data, dict):
            return None
        meta = extra_data.get(cls.META_KEY)
        if not isinstance(meta, dict):
            return None
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        return {
            "revision": int(meta.get("revision") or 0),
            "sourceSystem": meta.get("sourceSystem") or meta.get("source", {}).get("system"),
            "sourceRecordId": meta.get("sourceRecordId") or meta.get("source", {}).get("recordId"),
            "sourceRecordUrl": meta.get("sourceRecordUrl") or meta.get("source", {}).get("recordUrl"),
            "ticketUrl": (
                meta.get("ticketUrl")
                or meta.get("sourceRecordUrl")
                or (meta.get("source", {}) or {}).get("recordUrl")
            ),
            "sourceRevision": SyncUtil.safe_int(meta.get("sourceRevision")) or 0,
            "externalCreateTime": (
                meta.get("externalCreateTime")
                or (meta.get("source") or {}).get("externalCreateTime")
            ),
            "status": sync_state.get("status") or "pending",
            "publishReady": bool(sync_state.get("publish_ready", True)),
            "publishStatus": sync_state.get("publish_status") or cls.PUBLISH_STATUS_READY,
            "publishReason": sync_state.get("publish_reason") or "",
            "aiTaskStatus": sync_state.get("ai_task_status") or "",
            "groupPushSentOnce": bool(sync_state.get("group_push_sent_once", False)),
            "lastPulledAt": sync_state.get("last_pulled_at"),
            "lastConsumer": sync_state.get("last_consumer"),
            "automationStatus": automation.get("status"),
            "automationStep": automation.get("current_step"),
            "automationError": automation.get("last_error"),
        }

    @classmethod
    def set_publish_state(
        cls,
        meta: dict[str, Any],
        *,
        ready: bool,
        status: str,
        reason: str = "",
        ai_task_status: str | None = None,
    ) -> dict[str, Any]:
        """
        更新同步数据发布状态。
        :param meta: 同步元数据
        :param ready: 是否允许对外发布（内网拉取/群推送）
        :param status: 发布状态编码
        :param reason: 状态说明
        :param ai_task_status: AI任务状态
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["publish_ready"] = bool(ready)
        sync_state["publish_status"] = str(status or "").strip() or cls.PUBLISH_STATUS_READY
        sync_state["publish_reason"] = str(reason or "").strip()
        sync_state["publish_updated_at"] = SyncUtil.now_iso()
        if ai_task_status is not None:
            sync_state["ai_task_status"] = str(ai_task_status or "").strip()
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def is_publish_ready(cls, meta: dict[str, Any]) -> bool:
        """
        判断同步数据是否允许对外发布。
        :param meta: 同步元数据
        :return: 是否可发布
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        if "publish_ready" not in sync_state:
            return True
        return bool(sync_state.get("publish_ready"))

    @classmethod
    def can_recover_publish_state(cls, db: Session, *, ticket: Ticket, meta: dict[str, Any]) -> tuple[bool, str]:
        """
        判断未发布同步数据是否可恢复为可发布状态。
        :param db: 数据库会话
        :param ticket: 待检查工单
        :param meta: 同步元数据
        :return: (是否可恢复, 恢复原因)
        """
        if cls.is_publish_ready(meta):
            return False, "already_ready"
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        publish_status = str(sync_state.get("publish_status") or "").strip()
        if publish_status != cls.PUBLISH_STATUS_PROCESSING_AI:
            return False, f"publish_status_not_recoverable:{publish_status or '-'}"
        ai_pending, ai_status = cls.resolve_ai_pending_state(db, ticket_id=ticket.ticket_id, meta=meta)
        if ai_pending:
            return False, f"ai_still_pending:{ai_status or '-'}"
        return True, f"ai_not_pending:{ai_status or '-'}"

    @classmethod
    def ensure_publish_ready_for_pull(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        current_user: CurrentUserModel,
    ) -> tuple[Ticket, dict[str, Any], bool]:
        """
        拉取前自愈同步发布状态，避免服务重启后 processing_ai 长期卡住。
        :param db: 数据库会话
        :param ticket: 候选工单
        :param current_user: 当前用户
        :return: (刷新后的工单, 同步元数据, 是否已恢复)
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls.build_meta(extra_data)
        recoverable, recover_reason = cls.can_recover_publish_state(db, ticket=ticket, meta=meta)
        if not recoverable:
            return ticket, meta, False
        logger.warning(
            f"工单同步发布状态自愈: ticket_no={ticket.ticket_no}, "
            f"revision={meta.get('revision')}, reason={recover_reason}"
        )
        meta = cls.set_publish_state(
            meta,
            ready=True,
            status=cls.PUBLISH_STATUS_READY,
            reason="拉取前检测到无活动AI任务，自动恢复发布状态",
            ai_task_status=str((meta.get("sync_state") or {}).get("ai_task_status") or "").strip(),
        )
        ticket = cls.persist_sync_meta(
            db,
            ticket=ticket,
            meta=meta,
            update_by=_user_name(current_user),
        )
        return ticket, meta, True

    @classmethod
    def resolve_sync_scene_from_meta(cls, meta: dict[str, Any]) -> str:
        """
        从同步元数据解析工单最近一次入库的同步场景。
        优先读取入库时持久化的 sync_state.sync_scene；历史工单没有该字段时按来源系统推断：
        feishu_bitable_pull -> bitable_pull，manual_create -> manual_create，
        其余保持 external_sync（远端拉取的来源系统可配置，无法与外部推送稳定区分）。
        :param meta: 同步元数据
        :return: 同步场景编码
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        persisted_scene = str(sync_state.get("sync_scene") or "").strip()
        if persisted_scene in {"external_sync", "remote_pull", "bitable_pull", "manual_create"}:
            return persisted_scene
        source_system = str(
            meta.get("sourceSystem")
            or (meta.get("source") or {}).get("system")
            or ""
        ).strip()
        if source_system == "feishu_bitable_pull":
            return "bitable_pull"
        if source_system == "manual_create":
            return "manual_create"
        return "external_sync"

    @classmethod
    def is_group_push_sent_once(cls, meta: dict[str, Any]) -> bool:
        """
        判断工单是否已成功发送过群推送。
        :param meta: 同步元数据
        :return: 是否已发送过
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        return bool(sync_state.get("group_push_sent_once"))

    @classmethod
    def mark_group_push_sent_once(
        cls,
        meta: dict[str, Any],
        *,
        scene: str,
        revision: int,
    ) -> dict[str, Any]:
        """
        标记工单已成功发送过群推送（仅一次）。
        :param meta: 同步元数据
        :param scene: 触发场景
        :param revision: 同步修订号
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_sent_once"] = True
        sync_state["group_push_sent_at"] = SyncUtil.now_iso()
        sync_state["group_push_scene"] = str(scene or "").strip() or "external_sync"
        sync_state["group_push_revision"] = int(revision or 0)
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def append_group_push_message_refs(
        cls,
        meta: dict[str, Any],
        message_refs: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """
        记录群推送成功发送后的飞书消息 ID，供后续评论回帖定位话题。
        :param meta: 同步元数据
        :param message_refs: 飞书发送返回的消息明细
        :return: 更新后的同步元数据
        """
        if not isinstance(message_refs, list) or not message_refs:
            return meta
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        existing_refs = sync_state.get("group_push_message_refs")
        if not isinstance(existing_refs, list):
            existing_refs = []
        existing_message_ids = {
            str(item.get("messageId") or item.get("message_id") or "").strip()
            for item in existing_refs
            if isinstance(item, dict)
        }
        for item in message_refs:
            if not isinstance(item, dict):
                continue
            message_id = str(item.get("messageId") or item.get("message_id") or "").strip()
            if not message_id or message_id in existing_message_ids:
                continue
            existing_refs.append(
                {
                    "messageId": message_id,
                    "rootId": str(item.get("rootId") or item.get("root_id") or message_id).strip(),
                    "threadId": str(item.get("threadId") or item.get("thread_id") or "").strip(),
                    "chatId": str(item.get("chatId") or item.get("chat_id") or item.get("receiveId") or "").strip(),
                    "receiveId": str(item.get("receiveId") or item.get("receive_id") or "").strip(),
                    "receiveIdType": str(item.get("receiveIdType") or item.get("receive_id_type") or "").strip(),
                    "sentAt": SyncUtil.now_iso(),
                }
            )
            existing_message_ids.add(message_id)
        sync_state["group_push_message_refs"] = existing_refs[-20:]
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def mark_group_push_processing(
        cls,
        meta: dict[str, Any],
        *,
        scene: str,
        revision: int,
    ) -> dict[str, Any]:
        """
        标记工单群推送正在处理中，作为并发互斥锁。
        :param meta: 同步元数据
        :param scene: 触发场景
        :param revision: 同步修订号
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_processing"] = True
        sync_state["group_push_processing_at"] = SyncUtil.now_iso()
        sync_state["group_push_processing_scene"] = str(scene or "").strip() or "external_sync"
        sync_state["group_push_processing_revision"] = int(revision or 0)
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def clear_group_push_processing(cls, meta: dict[str, Any]) -> dict[str, Any]:
        """
        清理工单群推送处理中锁。
        :param meta: 同步元数据
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        sync_state["group_push_processing"] = False
        sync_state["group_push_processing_at"] = None
        sync_state["group_push_processing_scene"] = None
        sync_state["group_push_processing_revision"] = None
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def is_group_push_processing_locked(cls, meta: dict[str, Any]) -> tuple[bool, str]:
        """
        判断群推送处理锁是否生效。
        :param meta: 同步元数据
        :return: (是否锁定, 锁定原因)
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        if not bool(sync_state.get("group_push_processing")):
            return False, ""
        lock_time = SyncUtil.parse_datetime_value(sync_state.get("group_push_processing_at"))
        if lock_time is None:
            return True, "群推送处理中（锁时间缺失）"
        elapsed_seconds = (datetime.now() - lock_time).total_seconds()
        if elapsed_seconds > cls.GROUP_PUSH_LOCK_TIMEOUT_SECONDS:
            return False, ""
        return True, "群推送处理中"

    @classmethod
    def persist_group_push_meta_state(
        cls,
        db: Session,
        *,
        ticket_id: int,
        update_by: str,
        scene: str,
        acquire_lock: bool = False,
        clear_lock: bool = False,
        mark_sent_once: bool = False,
        message_refs: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, Ticket | None, dict[str, Any], str]:
        """
        在数据库行级锁内更新群推送状态，保障并发下的去重一致性。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param update_by: 更新人
        :param scene: 触发场景
        :param acquire_lock: 是否抢占群推送处理锁
        :param clear_lock: 是否清理群推送处理锁
        :param mark_sent_once: 是否标记已发送过
        :param message_refs: 飞书应用发送返回的消息明细
        :return: (是否更新成功, 工单对象, 最新元数据, 结果原因)
        """
        try:
            ticket = (
                db.query(Ticket)
                .filter(Ticket.ticket_id == ticket_id, Ticket.del_flag == "0")
                .with_for_update()
                .first()
            )
            if not ticket:
                db.rollback()
                return False, None, {}, "ticket_not_found"

            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls.build_meta(extra_data)
            if acquire_lock:
                if cls.is_group_push_sent_once(meta):
                    db.rollback()
                    return False, ticket, meta, "already_sent"
                locked, lock_reason = cls.is_group_push_processing_locked(meta)
                if locked:
                    db.rollback()
                    return False, ticket, meta, lock_reason or "group_push_processing"
                meta = cls.mark_group_push_processing(
                    meta,
                    scene=scene,
                    revision=int(meta.get("revision") or 0),
                )
            if clear_lock:
                meta = cls.clear_group_push_processing(meta)
            if mark_sent_once:
                meta = cls.mark_group_push_sent_once(
                    meta,
                    scene=scene,
                    revision=int(meta.get("revision") or 0),
                )
            meta = cls.append_group_push_message_refs(meta, message_refs)
            if acquire_lock or clear_lock or mark_sent_once or message_refs:
                refreshed_extra_data = cls.attach_meta(extra_data, meta)
                TicketDao.update_ticket(
                    db,
                    ticket.ticket_id,
                    {
                        "extra_data": refreshed_extra_data,
                        "update_by": update_by,
                        "update_time": datetime.now(),
                    },
                )
                db.commit()
                ticket = TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket
            else:
                db.rollback()
            return True, ticket, meta, "updated"
        except Exception:
            db.rollback()
            raise

    @classmethod
    def resolve_ai_pending_state(
        cls,
        db: Session,
        *,
        ticket_id: int,
        meta: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        判断工单是否仍处于 AI 处理中状态。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param meta: 同步元数据
        :return: (是否处理中, AI状态文本)
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        steps = automation.get("steps") if isinstance(automation.get("steps"), dict) else {}
        ai_step = steps.get("ai_analysis") if isinstance(steps.get("ai_analysis"), dict) else {}
        ai_step_status = str(ai_step.get("status") or "").strip().lower()
        ai_task_status = str(sync_state.get("ai_task_status") or "").strip().lower()
        ai_terminal_statuses = {
            TicketAiAnalysisStatus.SUCCESS.value,
            TicketAiAnalysisStatus.FAILED.value,
            TicketAiAnalysisStatus.CANCELED.value,
        }

        latest_task = TicketAiDao.get_latest_task_by_ticket_id(db, ticket_id)
        latest_status = str(getattr(latest_task, "status", "") or "").strip().lower()
        if latest_status in cls.AI_PENDING_TASK_STATUSES:
            return True, latest_status
        if latest_status in ai_terminal_statuses:
            return False, latest_status
        if ai_task_status in ai_terminal_statuses:
            return False, ai_task_status
        if ai_task_status in cls.AI_PENDING_TASK_STATUSES:
            return True, ai_task_status
        if ai_step_status in cls.AI_PENDING_AUTOMATION_STATUSES:
            return True, ai_task_status or ai_step_status
        if latest_status:
            return False, latest_status
        if ai_task_status:
            return False, ai_task_status
        return False, ai_step_status

    @classmethod
    def persist_sync_meta(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        update_by: str,
    ) -> Ticket:
        """
        将同步元数据回写到工单并提交。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param update_by: 更新人
        :return: 刷新后的工单对象
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        extra_data = cls.attach_meta(extra_data, meta)
        TicketDao.update_ticket(
            db,
            ticket.ticket_id,
            {
                "extra_data": extra_data,
                "update_by": update_by,
                "update_time": datetime.now(),
            },
        )
        db.commit()
        return TicketDao.get_ticket_by_id(db, ticket.ticket_id) or ticket

    @classmethod
    def send_auto_group_message_once(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        group_config: dict[str, Any],
        scene: str,
        update_by: str,
    ) -> tuple[dict[str, Any], Ticket, dict[str, Any]]:
        """
        自动触发群推送（仅发送一次）。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param group_config: 群推送配置
        :param scene: 触发场景
        :param update_by: 更新人
        :return: (推送结果, 刷新后的工单, 最新元数据)
        """

        skip_by_condition, condition_skip_reason = cls.should_skip_auto_group_push_by_condition(
            db=db,
            ticket=ticket,
            group_config=group_config,
        )
        if skip_by_condition:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={condition_skip_reason or '工单不满足推送条件'}"
            )
            return (
                {
                    "skipped": True,
                    "skipReason": condition_skip_reason or "工单不满足推送条件",
                    "scene": scene,
                },
                ticket,
                meta,
            )

        if not cls.is_publish_ready(meta):
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason=同步数据未发布就绪"
            )
            return (
                {"skipped": True, "skipReason": "同步数据未发布就绪", "scene": scene},
                ticket,
                meta,
            )
        if cls.is_group_push_sent_once(meta):
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason=工单已发送过群推送"
            )
            return (
                {"skipped": True, "skipReason": "工单已发送过群推送", "scene": scene},
                ticket,
                meta,
            )

        lock_acquired, locked_ticket, locked_meta, lock_reason = cls.persist_group_push_meta_state(
            db,
            ticket_id=ticket.ticket_id,
            update_by=update_by,
            scene=scene,
            acquire_lock=True,
        )
        if not lock_acquired:
            if lock_reason == "already_sent":
                logger.info(
                    f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"reason=工单已发送过群推送"
                )
                return (
                    {"skipped": True, "skipReason": "工单已发送过群推送", "scene": scene},
                    ticket,
                    meta,
                )
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={lock_reason or '群推送处理中'}"
            )
            return (
                {"skipped": True, "skipReason": lock_reason or "群推送处理中", "scene": scene},
                ticket,
                meta,
            )
        if locked_ticket:
            ticket = locked_ticket
        if locked_meta:
            meta = locked_meta

        sync_summary = cls.extract_sync_summary(
            cls.attach_meta(dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}, meta)
        ) or {}
        result: dict[str, Any] = {}
        mark_sent_once = False
        try:
            result = TicketSyncNotifyService.send_group_message_for_ticket(
                db,
                ticket=ticket,
                group_config=group_config,
                scene=scene,
                manual_trigger=False,
                sync_summary=sync_summary,
            )
            push_success_count = int(result.get("pushSuccessCount") or 0)
            app_success_count = int(result.get("chatSuccessCount") or 0)
            mark_sent_once = not bool(result.get("skipped")) and (push_success_count > 0 or app_success_count > 0)
            if mark_sent_once:
                logger.info(
                    f"自动群推送已标记去重: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"push_success_count={push_success_count}, app_success_count={app_success_count}"
                )
            elif not bool(result.get("skipped")):
                logger.warning(
                    f"自动群推送未产生成功发送，保持未去重状态: ticket_no={ticket.ticket_no}, scene={scene}, "
                    f"push_success_count={push_success_count}, app_success_count={app_success_count}"
                )
        finally:
            message_refs = (
                result.get("feishuMessageRefs")
                if isinstance(result.get("feishuMessageRefs"), list)
                else None
            )
            state_updated, refreshed_ticket, refreshed_meta, _ = cls.persist_group_push_meta_state(
                db,
                ticket_id=ticket.ticket_id,
                update_by=update_by,
                scene=scene,
                clear_lock=True,
                mark_sent_once=mark_sent_once,
                message_refs=message_refs,
            )
            if state_updated:
                if refreshed_ticket:
                    ticket = refreshed_ticket
                if refreshed_meta:
                    meta = refreshed_meta
        return result, ticket, meta

    @classmethod
    def finalize_publish_state_after_post_process(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        sync_scene: str,
        update_by: str,
    ) -> tuple[Ticket, dict[str, Any], dict[str, Any] | None]:
        """
        根据 AI 状态收敛发布状态，并按需触发自动群推送。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param sync_scene: 触发场景
        :param update_by: 更新人
        :return: (刷新后的工单, 元数据, 群推送结果)
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls.build_meta(extra_data)
        ai_pending, ai_status = cls.resolve_ai_pending_state(db, ticket_id=ticket.ticket_id, meta=meta)
        ai_task_status = str(ai_status or "").strip().lower()
        if ai_pending:
            meta = cls.set_publish_state(
                meta,
                ready=False,
                status=cls.PUBLISH_STATUS_PROCESSING_AI,
                reason="AI分析处理中，暂不对外发布",
                ai_task_status=ai_task_status or TicketAiAnalysisStatus.RUNNING.value,
            )
            ticket = cls.persist_sync_meta(
                db,
                ticket=ticket,
                meta=meta,
                update_by=update_by,
            )
            return ticket, meta, {"skipped": True, "skipReason": "AI分析处理中，暂不推送", "scene": sync_scene}

        reason = "AI分析已结束，允许对外发布" if ai_task_status else "后处理完成，允许对外发布"
        meta = cls.set_publish_state(
            meta,
            ready=True,
            status=cls.PUBLISH_STATUS_READY,
            reason=reason,
            ai_task_status=ai_task_status,
        )
        ticket = cls.persist_sync_meta(
            db,
            ticket=ticket,
            meta=meta,
            update_by=update_by,
        )
        config = TicketSyncConfigService.load_sync_config(db)
        scope_decision = TicketAutomationScopeService.evaluate_ticket(db, config, ticket)
        if not scope_decision.eligible:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, "
                f"reason={scope_decision.reason}, module_id={scope_decision.module_id}, "
                f"module_name={scope_decision.module_name!r}"
            )
            return ticket, meta, {
                "skipped": True,
                "skipReason": scope_decision.reason,
                "scene": sync_scene,
            }
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        if not cls._should_send_group_push_for_scene(group_config, sync_scene):
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, "
                f"reason=群推送配置未对当前场景启用"
            )
            return ticket, meta, {
                "skipped": True,
                "skipReason": f"群推送未对场景 {sync_scene} 启用",
                "scene": sync_scene,
            }
        group_push_result, ticket, meta = cls.send_auto_group_message_once(
            db,
            ticket=ticket,
            meta=meta,
            group_config=group_config,
            scene=sync_scene,
            update_by=update_by,
        )
        return ticket, meta, group_push_result

    @classmethod
    def finalize_sync_after_ai(
        cls,
        db: Session,
        *,
        ticket_id: int,
        ai_task_status: str,
        sync_scene: str = "",
        ai_task_id: int | None = None,
        ai_result_payload: dict[str, Any] | None = None,
        ai_error_message: str = "",
        follow_up_override: str = "",
    ) -> None:
        """
        在 AI 任务终态后收敛同步发布状态并补发一次自动群推送，
        随后按 aiResultFollowUp 配置把 AI 分析结果回帖到工单群话题。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param ai_task_status: AI任务状态
        :param sync_scene: 显式指定的同步场景；为空时从工单同步元数据解析最近一次入库场景
        :param ai_task_id: AI任务ID，用于结果回帖幂等
        :param ai_result_payload: AI分析结果载荷（成功时供回帖渲染）
        :param ai_error_message: AI失败原因（失败时供回帖渲染）
        :param follow_up_override: 结果回帖覆盖意图（follow 跟随全局 / on / off，手动触发时使用）
        :return: 无
        """
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            if not ticket:
                return
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls.build_meta(extra_data)
            if not str(sync_scene or "").strip():
                sync_scene = cls.resolve_sync_scene_from_meta(meta)
            logger.info(
                f"AI任务完成后群推送场景解析: ticket_no={ticket.ticket_no}, ticket_id={ticket_id}, "
                f"resolved_scene={sync_scene}"
            )
            normalized_status = str(ai_task_status or "").strip().lower()
            if normalized_status in cls.AI_PENDING_TASK_STATUSES:
                meta = cls.set_publish_state(
                    meta,
                    ready=False,
                    status=cls.PUBLISH_STATUS_PROCESSING_AI,
                    reason="AI分析处理中，暂不对外发布",
                    ai_task_status=normalized_status,
                )
                cls.persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
                return

            reason = (
                "AI分析成功，允许对外发布"
                if normalized_status == TicketAiAnalysisStatus.SUCCESS.value
                else "AI分析结束，允许对外发布"
            )
            meta = cls.set_publish_state(
                meta,
                ready=True,
                status=cls.PUBLISH_STATUS_READY,
                reason=reason,
                ai_task_status=normalized_status,
            )
            meta = cls._apply_ai_terminal_status_to_automation_step(meta, normalized_status)
            ticket = cls.persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
            config = TicketSyncConfigService.load_sync_config(db)
            scope_decision = TicketAutomationScopeService.evaluate_ticket(db, config, ticket)
            group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
            follow_up_config = (
                group_config.get("aiResultFollowUp")
                if isinstance(group_config.get("aiResultFollowUp"), dict)
                else {}
            )
            if not scope_decision.eligible:
                logger.info(
                    f"AI任务完成后自动群推送跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, "
                    f"reason={scope_decision.reason}, module_id={scope_decision.module_id}, "
                    f"module_name={scope_decision.module_name!r}"
                )
            else:
                # 先补发工单信息群消息（未发送过则发送并记录话题锚点），结果回帖依赖锚点。
                _, ticket, meta = cls.send_auto_group_message_once(
                    db,
                    ticket=ticket,
                    meta=meta,
                    group_config=group_config,
                    scene=sync_scene,
                    update_by="system",
                )
            # AI 结果话题回帖：不受自动化范围限制（结果回帖面向已在群里跟进的工单）；
            # 无锚点时按 noAnchorStrategy 处理：skip 跳过，send_then_reply 先补发工单信息再回帖
            #（补发自身带范围/场景/条件/去重全套判定，不会对历史已推送工单重复发送）。
            cls.send_ai_result_thread_reply(
                db,
                ticket=ticket,
                meta=meta,
                follow_up_config=follow_up_config,
                ai_task_status=normalized_status,
                ai_task_id=ai_task_id,
                ai_result_payload=ai_result_payload,
                ai_error_message=ai_error_message,
                override=follow_up_override,
                sync_scene=sync_scene,
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"AI任务完成后同步发布状态回写失败: "
                f"ticket_id={ticket_id}, ai_task_status={ai_task_status}, error={exc}"
            )

    @classmethod
    def _apply_ai_terminal_status_to_automation_step(cls, meta: dict[str, Any], ai_task_status: str) -> dict[str, Any]:
        """
        AI 任务到达终态后同步更新自动化步骤里的 ai_analysis 状态。
        自动化链路提交 AI 任务时只写入 queued，此前终态从不回写导致步骤状态永久停留在 queued；
        这里补齐回写，避免详情页和后续判断把已完成的 AI 当作处理中。
        :param meta: 同步元数据
        :param ai_task_status: AI任务终态状态
        :return: 更新后的同步元数据
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        automation = sync_state.get("automation") if isinstance(sync_state.get("automation"), dict) else {}
        steps = automation.get("steps") if isinstance(automation.get("steps"), dict) else {}
        ai_step = steps.get("ai_analysis") if isinstance(steps.get("ai_analysis"), dict) else {}
        if not ai_step:
            return meta
        status_map = {
            TicketAiAnalysisStatus.SUCCESS.value: "success",
            TicketAiAnalysisStatus.FAILED.value: "failed",
            TicketAiAnalysisStatus.CANCELED.value: "canceled",
        }
        step_status = status_map.get(str(ai_task_status or "").strip().lower())
        if not step_status:
            return meta
        ai_step["status"] = step_status
        ai_step["updated_at"] = SyncUtil.now_iso()
        steps["ai_analysis"] = ai_step
        automation["steps"] = steps
        if step_status == "failed":
            automation["status"] = "failed"
        elif all(
            (item or {}).get("status") not in {"queued", "running", "submitted"}
            for item in steps.values()
        ):
            automation["status"] = "completed"
        else:
            # 其他步骤仍在执行中，自动化整体保持 running。
            automation["status"] = "running"
        sync_state["automation"] = automation
        meta["sync_state"] = sync_state
        return meta

    # ---- AI 分析结果话题回帖（aiResultFollowUp）----

    AI_RESULT_SEND_ON_CHOICES = {"none", "success", "failed", "always"}

    @classmethod
    def should_send_ai_result_follow_up(
        cls,
        follow_up_config: dict[str, Any] | None,
        *,
        ai_task_status: str,
        override: str = "",
    ) -> tuple[bool, str]:
        """
        判断 AI 分析结果是否需要回帖到工单群话题。
        :param follow_up_config: aiResultFollowUp 配置
        :param ai_task_status: AI任务终态状态
        :param override: 手动触发时的覆盖意图（follow 跟随全局 / on 本次回帖 / off 本次不回帖）
        :return: (是否回帖, 判定原因)
        """
        config = follow_up_config if isinstance(follow_up_config, dict) else {}
        status = str(ai_task_status or "").strip().lower()
        override_mode = str(override or "").strip().lower()
        if override_mode in {"on", "off"}:
            if override_mode == "off":
                return False, "手动触发指定本次不回帖"
            # 手动指定本次回帖仍要求全局配置结构有效（sendOn 语义保留），仅跳过 enabled 总开关。
            send_on = str(config.get("sendOn") or "none").strip().lower()
            matched = cls._match_ai_result_send_on(send_on, status)
            return matched, f"手动触发指定本次回帖, sendOn={send_on}"
        if not bool(config.get("enabled")):
            return False, "AI结果回帖开关未启用"
        send_on = str(config.get("sendOn") or "none").strip().lower()
        if send_on not in cls.AI_RESULT_SEND_ON_CHOICES:
            send_on = "none"
        matched = cls._match_ai_result_send_on(send_on, status)
        return matched, f"sendOn={send_on}" if matched else f"sendOn={send_on} 不匹配当前终态"

    @classmethod
    def _match_ai_result_send_on(cls, send_on: str, ai_task_status: str) -> bool:
        """
        判断 sendOn 取值是否匹配 AI 任务终态；取消态任何取值都不推送。
        :param send_on: sendOn 配置取值
        :param ai_task_status: AI任务终态状态
        :return: 是否匹配
        """
        if send_on == "none":
            return False
        if ai_task_status == TicketAiAnalysisStatus.SUCCESS.value:
            return send_on in {"success", "always"}
        if ai_task_status == TicketAiAnalysisStatus.FAILED.value:
            return send_on in {"failed", "always"}
        # canceled 及未知状态一律不推送。
        return False

    @classmethod
    def is_ai_result_replied(
        cls,
        meta: dict[str, Any],
        *,
        task_id: int | None,
    ) -> bool:
        """
        判断指定 AI 任务是否已回帖过分析结果（按 task_id 幂等）。
        :param meta: 同步元数据
        :param task_id: AI任务ID
        :return: 是否已回帖
        """
        if not task_id:
            return False
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        replied_ids = sync_state.get("ai_result_reply_task_ids")
        if not isinstance(replied_ids, list):
            return False
        replied_keys = {str(item) for item in replied_ids}
        return str(task_id) in replied_keys

    @classmethod
    def mark_ai_result_replied(
        cls,
        meta: dict[str, Any],
        *,
        task_id: int | None,
    ) -> dict[str, Any]:
        """
        标记 AI 任务已回帖分析结果（按 task_id 幂等，保留最近 50 条防止元数据无限增长）。
        :param meta: 同步元数据
        :param task_id: AI任务ID
        :return: 更新后的同步元数据
        """
        if not task_id:
            return meta
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        replied_ids = sync_state.get("ai_result_reply_task_ids")
        if not isinstance(replied_ids, list):
            replied_ids = []
        task_key = str(task_id)
        if task_key not in {str(item) for item in replied_ids}:
            replied_ids.append(task_key)
        sync_state["ai_result_reply_task_ids"] = replied_ids[-50:]
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def _collect_ai_result_reply_targets(cls, meta: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从群推送锚点收集回帖目标（按 chatId 去重，工单信息发到几个群就回几个群）。
        :param meta: 同步元数据
        :return: 去重后的锚点列表
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        refs = sync_state.get("group_push_message_refs")
        if not isinstance(refs, list):
            return []
        targets: list[dict[str, Any]] = []
        seen_chat_ids: set[str] = set()
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            message_id = str(ref.get("messageId") or "").strip()
            if not message_id:
                continue
            chat_id = str(ref.get("chatId") or ref.get("receiveId") or "").strip()
            if chat_id and chat_id in seen_chat_ids:
                continue
            if chat_id:
                seen_chat_ids.add(chat_id)
            targets.append(
                {
                    "messageId": message_id,
                    "rootId": str(ref.get("rootId") or message_id).strip() or message_id,
                    "threadId": str(ref.get("threadId") or "").strip(),
                    "chatId": chat_id,
                }
            )
        return targets

    @classmethod
    def send_group_message_for_ai_reply(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        sync_scene: str = "",
    ) -> tuple[bool, Ticket, dict[str, Any], str]:
        """
        AI 结果回帖缺锚点时，先补发一条工单信息群消息建立话题。
        复用自动群推送的全套判定（自动化范围、场景开关、推送条件、仅一次去重、并发锁），
        只有真实发送成功才返回 True；被任何条件拦截或发送失败都返回 False 并带原因。
        注意：工单历史上已发送过（group_push_sent_once=true）时不会重复发送，
        适用于"从未推送过、想在群里建立话题"的工单。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param sync_scene: 同步场景，为空时从元数据解析
        :return: (是否发送成功, 刷新后的工单, 最新元数据, 未发送原因)
        """
        if not str(sync_scene or "").strip():
            sync_scene = cls.resolve_sync_scene_from_meta(meta)
        config = TicketSyncConfigService.load_sync_config(db)
        scope_decision = TicketAutomationScopeService.evaluate_ticket(db, config, ticket)
        if not scope_decision.eligible:
            reason = f"自动化范围不匹配: {scope_decision.reason}"
            logger.info(
                f"AI结果回帖补发群消息跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, reason={reason}"
            )
            return False, ticket, meta, reason
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        if not cls._should_send_group_push_for_scene(group_config, sync_scene):
            reason = f"群推送未对场景 {sync_scene} 启用"
            logger.info(
                f"AI结果回帖补发群消息跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, reason={reason}"
            )
            return False, ticket, meta, reason
        if cls.is_group_push_sent_once(meta):
            reason = "工单已发送过群推送（历史已有群消息，不重复发送）"
            logger.info(
                f"AI结果回帖补发群消息跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, reason={reason}"
            )
            return False, ticket, meta, reason
        if not cls.is_publish_ready(meta):
            reason = "同步数据未发布就绪"
            logger.info(
                f"AI结果回帖补发群消息跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, reason={reason}"
            )
            return False, ticket, meta, reason
        result, ticket, meta = cls.send_auto_group_message_once(
            db,
            ticket=ticket,
            meta=meta,
            group_config=group_config,
            scene=sync_scene,
            update_by="system",
        )
        if bool(result.get("skipped")):
            reason = str(result.get("skipReason") or "群推送被条件拦截")
            logger.info(
                f"AI结果回帖补发群消息跳过: ticket_no={ticket.ticket_no}, scene={sync_scene}, reason={reason}"
            )
            return False, ticket, meta, reason
        push_success_count = int(result.get("pushSuccessCount") or 0)
        app_success_count = int(result.get("chatSuccessCount") or 0)
        if push_success_count <= 0 and app_success_count <= 0:
            reason = "群推送未产生成功发送"
            logger.warning(
                f"AI结果回帖补发群消息未成功: ticket_no={ticket.ticket_no}, scene={sync_scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
            return False, ticket, meta, reason
        return True, ticket, meta, ""

    @classmethod
    def send_ai_result_thread_reply(
        cls,
        db: Session,
        *,
        ticket: Ticket,
        meta: dict[str, Any],
        follow_up_config: dict[str, Any] | None,
        ai_task_status: str,
        ai_task_id: int | None = None,
        ai_result_payload: dict[str, Any] | None = None,
        ai_error_message: str = "",
        override: str = "",
        sync_scene: str = "",
    ) -> tuple[dict[str, Any], Ticket, dict[str, Any]]:
        """
        AI 分析完成后，把分析结果回帖到工单群对应话题。
        回帖目标复用工单群推送锚点（与工单信息发送同一应用、同一优先级路由群）；
        无锚点时按 noAnchorStrategy 处理：skip 记日志跳过（默认），
        send_then_reply 先补发一条工单信息消息建立话题再回帖。
        :param db: 数据库会话
        :param ticket: 工单对象
        :param meta: 同步元数据
        :param follow_up_config: aiResultFollowUp 配置
        :param ai_task_status: AI任务终态状态
        :param ai_task_id: AI任务ID，用于幂等标记
        :param ai_result_payload: AI分析结果（成功时）
        :param ai_error_message: AI失败原因（失败时）
        :param override: 手动触发覆盖意图（follow 跟随全局 / on 本次回帖 / off 本次不回帖）
        :param sync_scene: 同步场景，noAnchorStrategy=send_then_reply 补发时用于范围与场景开关判定
        :return: (回帖结果, 刷新后的工单, 最新元数据)
        """
        should_reply, decision_reason = cls.should_send_ai_result_follow_up(
            follow_up_config,
            ai_task_status=ai_task_status,
            override=override,
        )
        if not should_reply:
            logger.info(
                f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                f"ai_task_status={ai_task_status}, reason={decision_reason}"
            )
            return ({"skipped": True, "skipReason": decision_reason, "taskId": ai_task_id}, ticket, meta)

        if cls.is_ai_result_replied(meta, task_id=ai_task_id):
            logger.info(
                f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id}, "
                f"reason=该AI任务已回帖过"
            )
            return ({"skipped": True, "skipReason": "该AI任务已回帖过", "taskId": ai_task_id}, ticket, meta)

        config = follow_up_config if isinstance(follow_up_config, dict) else {}
        targets = cls._collect_ai_result_reply_targets(meta)
        if not targets:
            no_anchor_strategy = str(config.get("noAnchorStrategy") or "skip").strip().lower()
            if no_anchor_strategy != "send_then_reply":
                # 默认策略 skip：无锚点（工单未发过群消息或锚点缺失）不新建话题，跳过并留痕，
                # 防止对历史已在群里跟进过的工单重复发送工单信息。
                logger.warning(
                    f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                    f"reason=工单无群消息锚点，无话题可回帖（noAnchorStrategy=skip）"
                )
                return (
                    {"skipped": True, "skipReason": "工单无群消息锚点，无话题可回帖", "taskId": ai_task_id},
                    ticket,
                    meta,
                )
            # 策略 send_then_reply：先补发工单信息消息建立话题（含范围/场景/条件/去重全套判定），
            # 补发成功后再回帖；补发被拦截或失败时回帖跳过，不留孤立结果消息。
            pushed, ticket, meta, push_reason = cls.send_group_message_for_ai_reply(
                db,
                ticket=ticket,
                meta=meta,
                sync_scene=sync_scene,
            )
            if not pushed:
                logger.warning(
                    f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                    f"reason=无锚点且补发工单信息未成功({push_reason or '-'})，不回帖"
                )
                return (
                    {
                        "skipped": True,
                        "skipReason": f"无锚点且补发工单信息未成功: {push_reason or '-'}",
                        "taskId": ai_task_id,
                    },
                    ticket,
                    meta,
                )
            targets = cls._collect_ai_result_reply_targets(meta)
            if not targets:
                logger.warning(
                    f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                    f"reason=补发后仍未取得话题锚点（发送成功但响应缺失message_id），不回帖"
                )
                return (
                    {"skipped": True, "skipReason": "补发后仍未取得话题锚点", "taskId": ai_task_id},
                    ticket,
                    meta,
                )
            logger.info(
                f"AI结果话题回帖补发完成: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                f"补发工单信息成功后继续回帖"
            )

        # 回帖凭证与工单信息推送一致：从群推送配置解析应用凭证。
        full_config = TicketSyncConfigService.load_sync_config(db)
        push_config = full_config.get("groupPush") if isinstance(full_config.get("groupPush"), dict) else {}
        app_id, app_secret = TicketSyncNotifyService.resolve_feishu_auth(push_config)
        if not app_id or not app_secret:
            logger.warning(
                f"AI结果话题回帖跳过: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                f"reason=飞书应用凭证未配置"
            )
            return (
                {"skipped": True, "skipReason": "飞书应用凭证未配置", "taskId": ai_task_id},
                ticket,
                meta,
            )

        content = TicketSyncNotifyService.build_ai_result_reply_content(
            ticket=ticket,
            follow_up_config=config,
            ai_task_status=ai_task_status,
            ai_result_payload=ai_result_payload,
            ai_error_message=ai_error_message,
        )
        reply_in_thread = bool(config.get("replyInThread", True))
        success_count = 0
        reply_refs: list[dict[str, Any]] = []
        for target in targets:
            try:
                reply_result = TicketSyncNotifyService.send_feishu_thread_reply(
                    app_id=app_id,
                    app_secret=app_secret,
                    message_id=target["messageId"],
                    content=content,
                    reply_in_thread=reply_in_thread,
                )
                success_count += 1
                reply_refs.append(
                    {
                        "chatId": target.get("chatId") or "",
                        "messageId": str(reply_result.get("messageId") or "").strip(),
                        "threadId": str(reply_result.get("threadId") or target.get("threadId") or "").strip(),
                    }
                )
            except Exception as exc:
                logger.warning(
                    f"AI结果话题回帖发送失败: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
                    f"chat_id={target.get('chatId') or '-'}, message_id={target['messageId']}, error={exc}"
                )
        logger.info(
            f"AI结果话题回帖完成: ticket_no={ticket.ticket_no}, task_id={ai_task_id or '-'}, "
            f"ai_task_status={ai_task_status}, target_count={len(targets)}, success_count={success_count}"
        )
        meta = cls.mark_ai_result_replied(meta, task_id=ai_task_id)
        ticket = cls.persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
        return (
            {
                "skipped": False,
                "taskId": ai_task_id,
                "targetCount": len(targets),
                "successCount": success_count,
                "replyRefs": reply_refs,
            },
            ticket,
            meta,
        )

    @classmethod
    def should_skip_auto_group_push_by_condition(
        cls,
        *,
        db: Session,
        ticket: Ticket,
        group_config: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """
        根据自定义条件表达式判断是否跳过自动群推送。

        :param db: 数据库会话。
        :param ticket: 工单对象。
        :param group_config: 群推送配置。
        :return: (是否跳过, 跳过原因)。
        """
        config = group_config if isinstance(group_config, dict) else {}
        auto_push_condition = (config.get("autoPushCondition") or "").strip()
        if not auto_push_condition:
            return False, None

        workflow_status = TicketDao.get_workflow_status_by_code(db, str(ticket.status or "").strip())
        status_name = str(getattr(workflow_status, "name", "") or "").strip()
        ticket_fields = _ticket_to_condition_fields(ticket, status_name=status_name)
        try:
            matched = evaluate_ticket_condition(auto_push_condition, ticket_fields)
        except SyntaxError as e:
            logger.warning(
                f"自动群推送条件表达式语法错误: ticket_no={ticket.ticket_no}, "
                f"condition={auto_push_condition!r}, error={e}"
            )
            return True, f"条件表达式语法错误: {e}"
        except Exception as e:
            logger.error(
                f"自动群推送条件表达式求值异常: ticket_no={ticket.ticket_no}, "
                f"condition={auto_push_condition!r}, error={e}"
            )
            return True, f"条件表达式求值异常: {e}"

        if matched:
            return False, None
        return True, "工单未满足自定义推送条件"


    @classmethod
    def send_group_push_by_ticket_no_services(
        cls,
        db: Session,
        *,
        ticket_no: str,
        push_ids: list[int] | None = None,
        message_template: str | None = None,
        force_push: bool = False,
        update_by: str = "system",
    ) -> dict[str, Any]:
        """
        手动按工单号发送群消息。

        :param db: 数据库会话。
        :param ticket_no: 工单号。
        :param push_ids: 覆盖推送渠道ID列表。
        :param message_template: 覆盖消息模板。
        :param force_push: 是否强制推送（忽略已推送状态）。
        :param update_by: 推送状态更新人。
        :return: 发送结果。
        """
        ticket = TicketDao.get_ticket_by_no(db, ticket_no)
        if not ticket:
            raise ValueError(f"工单不存在: {ticket_no}")
        config = TicketSyncConfigService.load_sync_config(db)
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        meta = cls.build_meta(extra_data)
        already_sent = cls.is_group_push_sent_once(meta)
        force_push_enabled = bool(force_push)
        manual_scene = "manual_force" if force_push_enabled else "manual"
        if already_sent and not force_push_enabled:
            logger.info(
                f"手动群推送跳过: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"reason=工单已发送过群推送且未开启强制推送"
            )
            return {
                "skipped": True,
                "skipReason": "工单已发送过群推送，未开启强制推送",
                "scene": manual_scene,
                "ticketNo": ticket.ticket_no,
                "alreadySent": True,
                "forcePush": False,
                "groupPushSentOnceUpdated": False,
            }
        sync_summary = cls.extract_sync_summary(ticket.extra_data) or {}
        logger.info(
            f"手动群推送触发: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
            f"force_push={force_push_enabled}, already_sent={already_sent}"
        )
        result = TicketSyncNotifyService.send_group_message_for_ticket(
            db,
            ticket=ticket,
            group_config=group_config,
            scene=manual_scene,
            manual_trigger=True,
            override_push_ids=push_ids,
            override_template=message_template,
            sync_summary=sync_summary,
        )
        push_success_count = int(result.get("pushSuccessCount") or 0)
        app_success_count = int(result.get("chatSuccessCount") or 0)
        group_push_state_updated = False
        if not bool(result.get("skipped")) and (push_success_count > 0 or app_success_count > 0):
            meta = cls.mark_group_push_sent_once(
                meta,
                scene=manual_scene,
                revision=int(meta.get("revision") or 0),
            )
            meta = cls.append_group_push_message_refs(
                meta,
                result.get("feishuMessageRefs") if isinstance(result.get("feishuMessageRefs"), list) else None,
            )
            ticket = cls.persist_sync_meta(
                db,
                ticket=ticket,
                meta=meta,
                update_by=str(update_by or "system"),
            )
            group_push_state_updated = True
            logger.info(
                f"手动群推送已更新去重状态: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        elif not bool(result.get("skipped")):
            logger.warning(
                f"手动群推送未产生成功发送，不更新去重状态: ticket_no={ticket.ticket_no}, scene={manual_scene}, "
                f"push_success_count={push_success_count}, app_success_count={app_success_count}"
            )
        return {
            **result,
            "ticketNo": ticket.ticket_no,
            "alreadySent": already_sent,
            "forcePush": force_push_enabled,
            "groupPushSentOnceUpdated": group_push_state_updated,
        }

    @classmethod
    def _should_send_group_push_for_scene(cls, group_config: dict[str, Any], sync_scene: str) -> bool:
        """
        判断群推送配置是否对当前场景启用。
        """
        scene_map = {
            "external_sync": "sendAfterExternalSync",
            "remote_pull": "sendAfterRemotePull",
            "bitable_pull": "sendAfterBitablePull",
            "manual_create": "sendAfterManualCreate",
        }
        config_key = scene_map.get(sync_scene)
        if config_key:
            return bool(group_config.get(config_key, False))
        return False


def _ticket_to_condition_fields(ticket: Ticket, *, status_name: str = "") -> dict:
    """
    将工单对象转为条件表达式求值用的字段字典。
    包含 Ticket 表所有业务字段，字段名与表达式中的引用名一致。

    :param ticket: 工单对象。
    :param status_name: 工作流状态显示名。
    :return: 条件表达式字段字典。

    注意：datetime/date 类型字段统一转为 ISO 字符串，确保与条件表达式中的
    字符串字面量（如 submit_time >= "2026-07-20"）可正常比较。
    ISO 格式字符串字典序等于时间序，>= / <= 比较结果正确。
    """
    from datetime import date, datetime

    raw = {
        "ticket_id": ticket.ticket_id,
        "ticket_no": ticket.ticket_no,
        "ticket_url": ticket.ticket_url,
        "title": ticket.title,
        "description": ticket.description,
        "project_id": ticket.project_id,
        "merchant_name": ticket.merchant_name,
        "module_id": ticket.module_id,
        "module_name": ticket.module_name,
        "category_id": ticket.category_id,
        "category_name": ticket.category_name,
        "issue_type_id": ticket.issue_type_id,
        "issue_type_name": ticket.issue_type_name,
        "status": ticket.status,
        "status_name": str(status_name or "").strip(),
        "customer_priority": ticket.customer_priority,
        "internal_priority": ticket.internal_priority,
        "severity": ticket.severity,
        "source": ticket.source,
        "reporter_id": ticket.reporter_id,
        "reporter_name": ticket.reporter_name,
        "current_assignee_id": ticket.current_assignee_id,
        "current_assignee_name": ticket.current_assignee_name,
        "first_line_assignee_id": ticket.first_line_assignee_id,
        "first_line_assignee_name": ticket.first_line_assignee_name,
        "internal_owner_id": ticket.internal_owner_id,
        "internal_owner_name": ticket.internal_owner_name,
        "is_problem": ticket.is_problem,
        "root_cause_type": ticket.root_cause_type,
        "solution_type": ticket.solution_type,
        "resolution_code": ticket.resolution_code,
        "resolution_name": ticket.resolution_name,
        "problem_pattern_code": ticket.problem_pattern_code,
        "problem_pattern_name": ticket.problem_pattern_name,
        "problem_pattern_confidence": ticket.problem_pattern_confidence,
        "problem_pattern_source": ticket.problem_pattern_source,
        "problem_pattern_verified": ticket.problem_pattern_verified,
        "issue_id": ticket.issue_id,
        "issue_relation_type": ticket.issue_relation_type,
        "issue_confirmed": ticket.issue_confirmed,
        "affected_version_id": ticket.affected_version_id,
        "planned_fix_version_id": ticket.planned_fix_version_id,
        "fixed_version_id": ticket.fixed_version_id,
        "released_version_id": ticket.released_version_id,
        "root_cause": ticket.root_cause,
        "solution": ticket.solution,
        "submit_time": ticket.submit_time,
        "started_at": ticket.started_at,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
        "first_response_at": ticket.first_response_at,
        "processed_at": ticket.processed_at,
        "released_at": ticket.released_at,
        "verified_at": ticket.verified_at,
        "total_process_seconds": ticket.total_process_seconds,
        "tags": ticket.tags,
        "del_flag": ticket.del_flag,
        "create_by": ticket.create_by,
        "update_by": ticket.update_by,
    }
    # 将 datetime/date 类型字段转为 ISO 字符串，确保与条件表达式中的字符串比较正常
    for key, value in raw.items():
        if isinstance(value, (datetime, date)):
            raw[key] = value.isoformat()
    return raw


