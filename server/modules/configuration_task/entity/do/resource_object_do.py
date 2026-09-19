"""配置任务资源对象 ORM 实体。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class ResourceObject(Base):
    """资源对象元数据；首期只登记 Agent 本地受控资源，不传输文件内容。"""

    __tablename__ = "configuration_task_resource_object"
    __table_args__ = (
        Index("idx_ct_resource_agent_status", "agent_code", "status", "resource_id"),
        Index("idx_ct_resource_expire", "status", "expires_at"),
    )

    resource_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="资源ID，Snowflake BIGINT",
    )
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="agent_local", comment="资源Provider：首期仅agent_local"
    )
    provider_execution_side: Mapped[str] = mapped_column(
        String(16), nullable=False, default="agent", comment="Provider执行侧：agent/server"
    )
    agent_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="执行Agent编码")
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, comment="Provider受控相对定位键")
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    mime_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="application/octet-stream",
        comment="MIME类型",
    )
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="文件字节数")
    checksum_algorithm: Mapped[str] = mapped_column(String(16), nullable=False, default="sha256", comment="校验算法")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA-256摘要")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="资源版本")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", comment="资源状态")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="资源过期时间")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="资源删除时间")
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
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="备注")
