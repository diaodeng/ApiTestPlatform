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
from modules.ticket.service.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.ticket_sync_notify_service import TicketSyncNotifyService
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
        # 检查主动拉取任务级群消息开关（bitable_pull.sendGroupMessage）
        ticket_extra = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
        bitable_pull_meta = (
            ticket_extra.get("bitable_pull")
            if isinstance(ticket_extra.get("bitable_pull"), dict)
            else {}
        )
        if bitable_pull_meta.get("sendGroupMessage") is False:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason=主动拉取任务级参数关闭了群消息推送"
            )
            return (
                {"skipped": True, "skipReason": "主动拉取任务级参数关闭了群消息推送", "scene": scene},
                ticket,
                meta,
            )

        skip_by_status, status_skip_reason = cls.should_skip_auto_group_push_by_status(
            ticket=ticket,
            group_config=group_config,
        )
        if skip_by_status:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={status_skip_reason or '工单状态不满足自动推送条件'}"
            )
            return (
                {
                    "skipped": True,
                    "skipReason": status_skip_reason or "工单状态不满足自动推送条件",
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
        skip_by_submit_time, submit_time_skip_reason = cls.should_skip_auto_group_push_by_submit_time(
            ticket=ticket,
            meta=meta,
            group_config=group_config,
        )
        if skip_by_submit_time:
            logger.info(
                f"自动群推送跳过: ticket_no={ticket.ticket_no}, scene={scene}, "
                f"reason={submit_time_skip_reason or '工单提交时间不满足自动推送起始时间'}"
            )
            return (
                {
                    "skipped": True,
                    "skipReason": submit_time_skip_reason or "工单提交时间不满足自动推送起始时间",
                    "scene": scene,
                },
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
        group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
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
        sync_scene: str = "external_sync",
    ) -> None:
        """
        在 AI 任务终态后收敛同步发布状态并补发一次自动群推送。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param ai_task_status: AI任务状态
        :param sync_scene: 触发场景
        :return: 无
        """
        try:
            ticket = TicketDao.get_ticket_by_id(db, ticket_id)
            if not ticket:
                return
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            meta = cls.build_meta(extra_data)
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
            ticket = cls.persist_sync_meta(db, ticket=ticket, meta=meta, update_by="system")
            config = TicketSyncConfigService.load_sync_config(db)
            group_config = config.get("groupPush") if isinstance(config.get("groupPush"), dict) else {}
            cls.send_auto_group_message_once(
                db,
                ticket=ticket,
                meta=meta,
                group_config=group_config,
                scene=sync_scene,
                update_by="system",
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                f"AI任务完成后同步发布状态回写失败: "
                f"ticket_id={ticket_id}, ai_task_status={ai_task_status}, error={exc}"
            )

    @classmethod
    def resolve_ticket_submit_time(cls, *, ticket: Ticket, meta: dict[str, Any] | None) -> datetime | None:
        """
        解析工单提交时间：优先外部 createTime，缺失时回退本地创建时间。

        :param ticket: 工单对象。
        :param meta: 同步元数据。
        :return: 可比较的提交时间，无法解析时返回 None。
        """
        sync_meta = meta if isinstance(meta, dict) else {}
        source_snapshot = sync_meta.get("source") if isinstance(sync_meta.get("source"), dict) else {}
        external_create_time = (
            sync_meta.get("externalCreateTime")
            or source_snapshot.get("externalCreateTime")
        )
        parsed_external_time = SyncUtil.parse_datetime_value(external_create_time)
        if parsed_external_time:
            return parsed_external_time
        return SyncUtil.parse_datetime_value(getattr(ticket, "create_time", None))

    @classmethod
    def resolve_group_push_auto_send_after_time(cls, group_config: dict[str, Any] | None) -> datetime | None:
        """
        解析自动群推送起始时间配置。

        :param group_config: 群推送配置。
        :return: 起始时间，未配置或解析失败时返回 None。
        """
        config = group_config if isinstance(group_config, dict) else {}
        return SyncUtil.parse_datetime_value(
            config.get("autoSendAfterTime")
            or config.get("auto_send_after_time")
        )

    @classmethod
    def normalize_group_push_auto_statuses(
        cls,
        value: Any,
        *,
        fallback: Any = None,
    ) -> list[str]:
        """
        归一化自动群推送状态条件配置。

        :param value: 原始状态条件，支持列表或逗号分隔字符串。
        :param fallback: 回退配置值。
        :return: 去重后的状态文本列表。
        """
        source_value = value
        if source_value is None:
            source_value = fallback
        if isinstance(source_value, str):
            source_list = [item.strip() for item in source_value.split(",")]
        elif isinstance(source_value, list):
            source_list = source_value
        else:
            source_list = []
        normalized: list[str] = []
        for item in source_list:
            status_text = str(item or "").strip()
            if status_text and status_text not in normalized:
                normalized.append(status_text)
        return normalized

    @classmethod
    def should_skip_auto_group_push_by_status(
        cls,
        *,
        ticket: Ticket,
        group_config: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """
        判断自动群推送是否因状态条件不满足而跳过。

        :param ticket: 工单对象。
        :param group_config: 群推送配置。
        :return: (是否跳过, 跳过原因)。
        """
        config = group_config if isinstance(group_config, dict) else {}
        auto_push_statuses = cls.normalize_group_push_auto_statuses(
            config.get("autoPushStatuses", config.get("auto_push_statuses")),
        )
        if not auto_push_statuses:
            return False, None
        ticket_status = str(getattr(ticket, "status", "") or "").strip()
        if ticket_status in auto_push_statuses:
            return False, None
        return True, f"工单状态({ticket_status or '-'})未命中自动推送状态条件"

    @classmethod
    def should_skip_auto_group_push_by_submit_time(
        cls,
        *,
        ticket: Ticket,
        meta: dict[str, Any] | None,
        group_config: dict[str, Any] | None,
    ) -> tuple[bool, str | None]:
        """
        判断自动群推送是否因“起始提交时间”配置而跳过。

        :param ticket: 工单对象。
        :param meta: 同步元数据。
        :param group_config: 群推送配置。
        :return: (是否跳过, 跳过原因)。
        """
        auto_send_after_time = cls.resolve_group_push_auto_send_after_time(group_config)
        if not auto_send_after_time:
            return False, None
        submit_time = cls.resolve_ticket_submit_time(ticket=ticket, meta=meta)
        if submit_time is None:
            return False, None
        if submit_time <= auto_send_after_time:
            return (
                True,
                f"工单提交时间({submit_time.isoformat()})未晚于自动推送起始时间({auto_send_after_time.isoformat()})",
            )
        return False, None


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


