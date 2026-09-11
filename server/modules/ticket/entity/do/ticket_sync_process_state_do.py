from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class TicketSyncProcessState(Base):
    """
    工单同步过程状态表（一工单一行），承接发布状态与群推送执行状态两个域。

    背景（阶段 2b）：这些状态原存 ticket.extra_data JSON，整包读改写下
    AI 终态回调与后处理批次并发互相覆盖（INC00001934853R 实测），且群推送
    去重锁依赖锁 ticket 行。拆宽表后状态为列级 UPDATE，去重锁锁本表行。
    注意：automation 步骤状态保留在 sync_state.automation JSON，不在本表。
    """

    __tablename__ = "ticket_sync_process_state"
    __table_args__ = (
        Index("idx_ticket_sync_process_ready", "publish_ready", "publish_status"),
    )

    ticket_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment="工单ID（一工单一行）")
    # ---- 发布域：AI 终态/后处理写，delivery 拉取与详情读 ----
    publish_ready: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否允许对外发布（内网拉取/群推送），1允许 0不允许"
    )
    publish_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ready", comment="发布状态编码：ready/processing_ai"
    )
    publish_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="状态说明")
    publish_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布状态更新时间")
    ai_task_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="", comment="最近一次AI任务终态状态"
    )
    # ---- 群推送执行域：群推送链路写（去重与并发锁） ----
    push_sent_once: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="工单信息群消息是否已成功发送过（工单级仅一次标记）"
    )
    push_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近一次群推送成功时间")
    push_scene: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="最近一次群推送触发场景")
    push_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="群推送状态修订号")
    push_processing: Mapped[bool] = mapped_column(Boolean, default=False, comment="群推送处理锁标记")
    push_processing_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="群推送处理锁获取时间"
    )
    push_processing_scene: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="群推送处理锁场景"
    )
    push_processing_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="群推送处理锁修订号"
    )
    update_by: Mapped[str] = mapped_column(String(100), nullable=False, default="system", comment="最近更新人")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
