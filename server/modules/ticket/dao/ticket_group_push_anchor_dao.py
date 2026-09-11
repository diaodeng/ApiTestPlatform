from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_group_push_anchor_do import TicketGroupPushAnchor


class TicketGroupPushAnchorDao:
    """
    工单群推送话题锚点数据访问层，只做锚点的查询与持久化。
    锚点是 AI 结果回帖、飞书评论入站匹配和本地评论出站回复的话题定位依据。
    """

    # 每工单保留的锚点条数上限，对齐拆表前 extra_data JSON 列表的 20 条截断语义。
    MAX_ANCHORS_PER_TICKET = 20

    @classmethod
    def _normalize_ref(cls, item: dict) -> dict | None:
        """
        归一化群推送返回的消息明细（feishuMessageRefs 元素，camelCase 键）为锚点字段。
        :param item: 飞书发送返回的消息明细
        :return: 锚点字段字典；缺 message_id 返回 None
        """
        message_id = str(item.get("messageId") or item.get("message_id") or "").strip()
        if not message_id:
            return None
        return {
            "chat_id": str(
                item.get("chatId") or item.get("chat_id") or item.get("receiveId") or item.get("receive_id") or ""
            ).strip(),
            "message_id": message_id,
            "root_id": str(item.get("rootId") or item.get("root_id") or message_id).strip(),
            "thread_id": str(item.get("threadId") or item.get("thread_id") or "").strip(),
            "receive_id": str(item.get("receiveId") or item.get("receive_id") or "").strip(),
            "receive_id_type": str(item.get("receiveIdType") or item.get("receive_id_type") or "").strip(),
        }

    @classmethod
    def insert_anchors(cls, db: Session, ticket_id: int, message_refs: list[dict] | None) -> int:
        """
        批量写入工单群消息锚点，按 message_id 去重（表内已有与本次入参内重复均跳过）。
        由调用方事务边界统一提交；插入数量超过单工单上限时按时间保留最新。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param message_refs: 飞书发送返回的消息明细列表（feishuMessageRefs）
        :return: 实际新增条数
        """
        if not ticket_id or not isinstance(message_refs, list):
            return 0
        normalized: list[dict] = []
        seen_message_ids: set[str] = set()
        for item in message_refs:
            if not isinstance(item, dict):
                continue
            fields = cls._normalize_ref(item)
            if not fields or fields["message_id"] in seen_message_ids:
                continue
            seen_message_ids.add(fields["message_id"])
            normalized.append(fields)
        if not normalized:
            return 0
        existing_ids = {
            str(row[0])
            for row in db.query(TicketGroupPushAnchor.message_id)
            .filter(TicketGroupPushAnchor.ticket_id == ticket_id)
            .all()
        }
        inserted = 0
        now = datetime.now()
        for fields in normalized:
            if fields["message_id"] in existing_ids:
                continue
            db.add(TicketGroupPushAnchor(ticket_id=ticket_id, create_time=now, **fields))
            existing_ids.add(fields["message_id"])
            inserted += 1
        if inserted:
            cls.trim_anchors_by_ticket_id(db, ticket_id)
        return inserted

    @classmethod
    def trim_anchors_by_ticket_id(cls, db: Session, ticket_id: int) -> int:
        """
        裁剪工单锚点至保留上限（按写入时间倒序保留最新），防止无限增长。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 删除条数
        """
        keep_ids = [
            row[0]
            for row in db.query(TicketGroupPushAnchor.id)
            .filter(TicketGroupPushAnchor.ticket_id == ticket_id)
            .order_by(TicketGroupPushAnchor.create_time.desc(), TicketGroupPushAnchor.id.desc())
            .limit(cls.MAX_ANCHORS_PER_TICKET)
            .all()
        ]
        if not keep_ids:
            return 0
        deleted = (
            db.query(TicketGroupPushAnchor)
            .filter(
                TicketGroupPushAnchor.ticket_id == ticket_id,
                TicketGroupPushAnchor.id.notin_(keep_ids),
            )
            .delete(synchronize_session=False)
        )
        return int(deleted or 0)

    @classmethod
    def list_anchors_by_ticket_id(cls, db: Session, ticket_id: int, limit: int = 20) -> list[TicketGroupPushAnchor]:
        """
        查询工单的群消息锚点（按写入时间正序，与拆表前 JSON 列表顺序语义一致）。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param limit: 最多返回条数
        :return: 锚点 ORM 对象列表
        """
        if not ticket_id:
            return []
        rows = (
            db.query(TicketGroupPushAnchor)
            .filter(TicketGroupPushAnchor.ticket_id == ticket_id)
            .order_by(TicketGroupPushAnchor.create_time.asc(), TicketGroupPushAnchor.id.asc())
            .limit(limit)
            .all()
        )
        return list(rows)

    @classmethod
    def match_ticket_ids_by_message_values(cls, db: Session, values: list[str]) -> list[int]:
        """
        按飞书消息上下文值（rootId/threadId/messageId）索引匹配锚点所属工单。
        供评论入站匹配使用，替代拆表前"全表扫描工单逐单解析 JSON"的 O(全表) 实现。
        :param db: 数据库会话
        :param values: 待匹配的消息 ID 值集合
        :return: 命中的工单 ID 列表（去重，按锚点时间倒序）
        """
        normalized = [str(item or "").strip() for item in values if str(item or "").strip()]
        if not normalized:
            return []
        rows = (
            db.query(TicketGroupPushAnchor.ticket_id)
            .filter(
                or_(
                    TicketGroupPushAnchor.message_id.in_(normalized),
                    TicketGroupPushAnchor.root_id.in_(normalized),
                    TicketGroupPushAnchor.thread_id.in_(normalized),
                )
            )
            .order_by(TicketGroupPushAnchor.create_time.desc())
            .distinct()
            .all()
        )
        return [int(row[0]) for row in rows]
