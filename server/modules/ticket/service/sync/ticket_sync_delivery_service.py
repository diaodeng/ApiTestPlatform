from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.vo.ticket_vo import TicketSyncAckRequestModel, TicketSyncPullQueryModel
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.util.sync_util import SyncUtil
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.common_util import CamelCaseUtil


class TicketSyncDeliveryService:
    """
    工单同步交付服务。

    只负责 pending 拉取、消费者交付状态、ack 回执和同步摘要构造，不处理入库、
    AI、通知或自动化副作用。
    """

    PUBLISH_STATUS_READY = "ready"

    @classmethod
    def extract_sync_summary(cls, extra_data: Any) -> dict[str, Any] | None:
        """
        从工单扩展字段中提取同步摘要。
        :param extra_data: 工单 extra_data。
        :return: 前端和远端消费方使用的同步摘要，不存在同步元数据时返回 None。
        """
        if not isinstance(extra_data, dict):
            return None
        meta = extra_data.get(TicketSyncPayloadService.META_KEY)
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
    def update_consumer_state(
        cls,
        meta: dict[str, Any],
        *,
        consumer: str,
        revision: int,
        batch_id: str,
        status: str = "delivered",
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        更新消费者同步状态。
        :param meta: 同步元数据。
        :param consumer: 消费者标识。
        :param revision: 本次交付版本。
        :param batch_id: 批次ID。
        :param status: 交付状态，pulled 表示已返回但待回执，只有 delivered/success 才确认交付。
        :param message: 回执说明。
        :param detail: 回执明细。
        :return: 更新后的同步元数据。
        """
        sync_state = meta.get("sync_state") if isinstance(meta.get("sync_state"), dict) else {}
        consumers = sync_state.get("consumers") if isinstance(sync_state.get("consumers"), dict) else {}
        previous_consumer_state = consumers.get(consumer) if isinstance(consumers.get(consumer), dict) else {}
        normalized_status = str(status or "").strip().lower() or "delivered"
        delivered_revision = int(previous_consumer_state.get("delivered_revision") or 0)
        if normalized_status in {"delivered", "success", "succeeded"}:
            delivered_revision = max(delivered_revision, int(revision or 0))
        elif int(revision or 0) > 0 and delivered_revision == int(revision or 0):
            delivered_revision = max(int(revision or 0) - 1, 0)
        consumers[consumer] = {
            "status": status,
            "delivered_revision": delivered_revision,
            "last_revision": int(revision or 0),
            "delivered_at": SyncUtil.now_iso(),
            "batch_id": batch_id,
            "message": message,
            "detail": detail,
        }
        sync_state.update(
            {
                "status": status,
                "last_pulled_at": SyncUtil.now_iso(),
                "last_consumer": consumer,
                "last_batch_id": batch_id,
                "consumers": consumers,
            }
        )
        meta["sync_state"] = sync_state
        return meta

    @classmethod
    def pull_pending_tickets(
        cls,
        db: Session,
        query: TicketSyncPullQueryModel,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        拉取指定消费者待交付的工单版本。
        :param db: 数据库会话。
        :param query: 拉取查询条件。
        :param current_user: 当前用户。
        :return: 本批次拉取结果。
        """
        rows = TicketDao.get_tickets_for_sync(
            db,
            consumer=query.consumer,
            limit=query.limit,
            include_closed=query.include_closed,
        )
        batch_id = f"{query.consumer}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        payload_rows: list[dict[str, Any]] = []
        for ticket in rows:
            ticket, meta, _ = TicketSyncGroupPushService.ensure_publish_ready_for_pull(
                db,
                ticket=ticket,
                current_user=current_user,
            )
            if not TicketSyncGroupPushService.is_publish_ready(meta):
                continue
            extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
            revision = int(meta.get("revision") or 0)
            meta = cls.update_consumer_state(
                meta,
                consumer=query.consumer,
                revision=revision,
                batch_id=batch_id,
                status="pulled",
                message="已返回给消费者，等待成功回执确认",
            )
            extra_data = TicketSyncPayloadService.attach_meta(extra_data, meta)
            TicketDao.update_ticket(
                db,
                ticket.ticket_id,
                {
                    "extra_data": extra_data,
                    "update_by": _user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            item = TicketService.get_ticket_detail_services(db, ticket.ticket_id) or CamelCaseUtil.transform_result(
                ticket
            )
            item["syncRevision"] = revision
            sync_summary = cls.extract_sync_summary(extra_data)
            item["syncSummary"] = sync_summary
            item["ticketUrl"] = str(
                item.get("ticketUrl")
                or item.get("ticket_url")
                or (sync_summary.get("ticketUrl") if isinstance(sync_summary, dict) else "")
                or (sync_summary.get("sourceRecordUrl") if isinstance(sync_summary, dict) else "")
                or ""
            ).strip() or None
            if isinstance(sync_summary, dict) and sync_summary.get("externalCreateTime"):
                item["externalCreateTime"] = sync_summary.get("externalCreateTime")
            payload_rows.append(item)
        db.commit()
        return {
            "consumer": query.consumer,
            "batchId": batch_id,
            "count": len(payload_rows),
            "items": payload_rows,
        }

    @classmethod
    def ack_sync_delivery(
        cls,
        db: Session,
        request: TicketSyncAckRequestModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        回写同步消费者处理结果。
        :param db: 数据库会话。
        :param request: 回执请求。
        :param current_user: 当前用户。
        :return: 更新结果。
        """
        updated = 0
        try:
            for item in request.items:
                ticket = TicketDao.get_ticket_by_id(db, item.ticket_id)
                if not ticket:
                    continue
                extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
                meta = TicketSyncPayloadService.build_meta(extra_data)
                meta = cls.update_consumer_state(
                    meta,
                    consumer=request.consumer,
                    revision=item.sync_revision,
                    batch_id=(meta.get("sync_state", {}) or {}).get("last_batch_id") or "",
                    status=item.delivery_status,
                    message=item.message,
                    detail=item.detail,
                )
                extra_data = TicketSyncPayloadService.attach_meta(extra_data, meta)
                TicketDao.update_ticket(
                    db,
                    ticket.ticket_id,
                    {
                        "extra_data": extra_data,
                        "update_by": _user_name(current_user),
                        "update_time": datetime.now(),
                    },
                )
                updated += 1
            db.commit()
            return CrudResponseModel(is_success=True, message="同步回执已更新", result={"updated": updated})
        except Exception:
            db.rollback()
            raise
