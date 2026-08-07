from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import TicketComment, TicketEvent, TicketMessage
from modules.ticket.enums.ticket_enums import TicketEventType


class TicketCommentCoreService:
    """
    工单评论底层写入服务。

    该服务只依赖 DAO、实体和枚举，供工单主服务、外部同步、飞书消息同步复用，避免高层服务相互导入。
    """

    @classmethod
    def add_message(
        cls,
        query_db: Session,
        *,
        ticket_id: int,
        role: str,
        message_type: str,
        content: str,
        created_by_id: int | None = None,
        created_by_name: str = "",
        attachments: dict[str, Any] | list[dict[str, Any]] | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
        create_time: datetime | None = None,
    ) -> TicketMessage:
        """
        新增工单消息流记录。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param role: 消息角色
        :param message_type: 消息类型
        :param content: 消息正文
        :param created_by_id: 创建人ID
        :param created_by_name: 创建人名称
        :param attachments: 附件或引用信息
        :param reference_type: 关联对象类型
        :param reference_id: 关联对象ID
        :param create_time: 创建时间
        :return: 消息对象
        """
        return TicketDao.add_message(
            query_db,
            TicketMessage(
                ticket_id=ticket_id,
                role=role,
                message_type=message_type,
                content=str(content or "").strip(),
                attachments=attachments,
                reference_type=reference_type,
                reference_id=reference_id,
                created_by_id=created_by_id,
                created_by_name=created_by_name or "system",
                create_time=create_time or datetime.now(),
            ),
        )

    @classmethod
    def upsert_synced_comment(
        cls,
        query_db: Session,
        *,
        ticket_id: int,
        content: str,
        user_name: str,
        source_type: str,
        source_system: str,
        source_record_id: str,
        source_field: str,
        source_segment_key: str,
        source_segment_index: int,
        source_content_hash: str,
        external_created_at: datetime | None = None,
        attachments: dict[str, Any] | list[dict[str, Any]] | None = None,
        is_internal: bool = False,
    ) -> tuple[TicketComment | None, str]:
        """
        按外部分段幂等键新增或更新同步评论，本地评论不会被覆盖。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param content: 评论内容
        :param user_name: 评论人名称
        :param source_type: 来源类型，如 feishu_bitable
        :param source_system: 来源系统
        :param source_record_id: 来源记录ID
        :param source_field: 来源字段
        :param source_segment_key: 外部分段幂等键
        :param source_segment_index: 外部分段序号
        :param source_content_hash: 外部内容哈希
        :param external_created_at: 外部评论时间
        :param attachments: 评论附件或引用
        :param is_internal: 是否内部评论
        :return: (评论对象, 动作 created/updated/skipped)
        """
        normalized_content = str(content or "").strip()
        normalized_key = str(source_segment_key or "").strip()
        if not normalized_content or not normalized_key:
            return None, "skipped"
        existing = TicketDao.get_comment_by_source_segment_key(
            query_db,
            ticket_id=ticket_id,
            source_segment_key=normalized_key,
        )
        now = datetime.now()
        source_payload = {
            "source_type": str(source_type or "external").strip() or "external",
            "source_system": str(source_system or "").strip(),
            "source_record_id": str(source_record_id or "").strip(),
            "source_field": str(source_field or "").strip(),
            "source_segment_key": normalized_key,
            "source_segment_index": int(source_segment_index or 0),
            "source_content_hash": str(source_content_hash or "").strip(),
            "external_created_at": external_created_at,
            "attachments": attachments,
            "is_internal": bool(is_internal),
        }
        if existing:
            if (
                str(existing.source_content_hash or "") == source_payload["source_content_hash"]
                and str(existing.content or "").strip() == normalized_content
                and (existing.attachments or None) == (attachments or None)
            ):
                return existing, "skipped"
            TicketDao.update_comment(
                query_db,
                existing.id,
                {
                    "user_name": str(user_name or "").strip() or existing.user_name or "外部同步",
                    "content": normalized_content,
                    **source_payload,
                },
            )
            TicketDao.update_message_by_reference(
                query_db,
                reference_type="comment",
                reference_id=existing.id,
                data={
                    "content": normalized_content,
                    "attachments": {
                        "is_internal": bool(is_internal),
                        "source_type": source_payload["source_type"],
                        "source_system": source_payload["source_system"],
                        "source_record_id": source_payload["source_record_id"],
                        "source_field": source_payload["source_field"],
                        "source_segment_key": normalized_key,
                        "source_segment_index": source_payload["source_segment_index"],
                        "source_content_hash": source_payload["source_content_hash"],
                        "comment_attachments": attachments,
                    },
                    "created_by_name": str(user_name or "").strip() or existing.user_name or "外部同步",
                },
            )
            query_db.flush()
            refreshed = TicketDao.get_comment_by_source_segment_key(
                query_db,
                ticket_id=ticket_id,
                source_segment_key=normalized_key,
            )
            return refreshed or existing, "updated"

        if source_payload["source_content_hash"]:
            hash_existing = TicketDao.get_comment_by_source_content_hash(
                query_db,
                ticket_id=ticket_id,
                source_content_hash=source_payload["source_content_hash"],
            )
            if hash_existing and str(hash_existing.content or "").strip() == normalized_content:
                return hash_existing, "skipped"

        comment = TicketDao.add_comment(
            query_db,
            TicketComment(
                ticket_id=ticket_id,
                user_id=None,
                user_name=str(user_name or "").strip() or "外部同步",
                content=normalized_content,
                create_time=external_created_at or now,
                **source_payload,
            ),
        )
        cls.add_message(
            query_db,
            ticket_id=ticket_id,
            role="user",
            message_type="external_comment",
            content=normalized_content,
            created_by_id=None,
            created_by_name=str(user_name or "").strip() or "外部同步",
            attachments={
                "is_internal": bool(is_internal),
                "source_type": source_payload["source_type"],
                "source_system": source_payload["source_system"],
                "source_record_id": source_payload["source_record_id"],
                "source_field": source_payload["source_field"],
                "source_segment_key": normalized_key,
                "source_segment_index": source_payload["source_segment_index"],
                "source_content_hash": source_payload["source_content_hash"],
                "comment_attachments": attachments,
            },
            reference_type="comment",
            reference_id=comment.id,
            create_time=comment.create_time,
        )
        TicketDao.add_event(
            query_db,
            TicketEvent(
                ticket_id=ticket_id,
                event_type=TicketEventType.COMMENTED.value,
                operator_id=None,
                operator_name=str(user_name or "").strip() or "外部同步",
                content=normalized_content,
                event_data={
                    "comment_id": comment.id,
                    "is_internal": bool(is_internal),
                    "source_type": source_payload["source_type"],
                    "source_record_id": source_payload["source_record_id"],
                    "source_segment_key": normalized_key,
                },
                create_time=comment.create_time,
            ),
        )
        return comment, "created"
