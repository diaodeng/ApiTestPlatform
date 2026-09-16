from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class TicketGroupPushAnchor(Base):
    """
    工单群推送话题锚点表，记录工单信息群消息发送后返回的飞书消息明细。

    供三类链路定位话题：AI 结果回帖（send_ai_result_thread_reply）、
    飞书话题评论入站匹配（_match_ticket_by_message_context）、本地评论出站回复（_resolve_feishu_reply_anchor）。
    2026-09 前锚点存于 ticket.extra_data JSON，被外部同步更新链路的 build_meta 白名单重建
    静默擦除（INC00001934853/R 回帖丢失根因），现拆为独立表，不再参与 extra_data 整包读改写。
    """

    __tablename__ = "ticket_group_push_anchor"
    __table_args__ = (
        UniqueConstraint("message_id", name="uk_ticket_group_push_anchor_message"),
        Index("idx_ticket_group_push_anchor_ticket", "ticket_id", "create_time"),
        Index("idx_ticket_group_push_anchor_root", "root_id"),
        Index("idx_ticket_group_push_anchor_thread", "thread_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="锚点ID"
    )
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="工单ID")
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="飞书群chat_id")
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="飞书消息ID（回帖/入站匹配锚点）")
    root_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="飞书根消息ID（话题根）")
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="飞书话题ID")
    receive_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="发送目标ID")
    receive_id_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", comment="发送目标类型：chat_id/email"
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="写入时间")
