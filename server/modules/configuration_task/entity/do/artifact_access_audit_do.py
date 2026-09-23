"""配置任务产物访问审计 ORM 实体。"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class ConfigurationTaskArtifactAccessAudit(Base):
    """产物预览/下载审计；只保存标识、结果和脱敏错误摘要，不保存正文。"""

    __tablename__ = "configuration_task_artifact_access_audit"
    __table_args__ = (
        Index("idx_ct_artifact_access_audit_artifact", "artifact_id", "create_time"),
        Index("idx_ct_artifact_access_audit_run", "task_run_id", "create_time"),
    )

    audit_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="审计ID，Snowflake BIGINT",
    )
    artifact_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="产物ID")
    task_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="运行ID")
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="资源ID")
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="动作：preview/download")
    operator: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="操作者")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否成功")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="稳定错误码")
    audit_message: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="脱敏审计摘要")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="审计时间")
