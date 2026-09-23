"""配置任务资源传输 ORM 实体。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base


class ResourceTransfer(Base):
    """记录一次 Agent 资源发布传输及其连接归属。"""

    __tablename__ = "configuration_task_resource_transfer"
    __table_args__ = (
        Index("idx_ct_transfer_resource_status", "resource_id", "status"),
        Index("idx_ct_transfer_agent_status", "agent_code", "status"),
        Index("idx_ct_transfer_expire", "status", "expires_at"),
    )

    transfer_id: Mapped[str] = mapped_column(String(128), primary_key=True, nullable=False, comment="传输ID")
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="资源ID，关联资源对象")
    agent_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="目标Agent编码")
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="Agent连接会话ID")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", comment="传输状态")
    expected_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="预期文件大小")
    expected_sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="预期SHA-256")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="资源版本")
    received_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="最近确认接收字节数")
    received_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="最近确认分片数")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="传输过期时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="最近错误码")
    error_message: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="最近错误摘要")
    create_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="更新者")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )
    last_audit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近审计时间")
    audit_message: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="审计摘要")
