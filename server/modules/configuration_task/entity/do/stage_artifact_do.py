"""配置任务阶段 ORM 实体：版本阶段定义与运行阶段实例。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker

STAGE_MODES = ("READ", "PREPARE_WRITE", "WRITE", "VERIFY")
STAGE_STATUSES = ("PENDING", "WAITING_APPROVAL", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", "CANCELLED")


class ConfigurationTaskStage(Base):
    """版本阶段定义：发布版本时从步骤列表切分生成，随版本冻结不可变。"""

    __tablename__ = "configuration_task_stage"
    __table_args__ = (
        UniqueConstraint("version_id", "stage_key", name="uk_ct_stage_version_key"),
        Index("idx_ct_stage_version_order", "version_id", "stage_order"),
    )

    stage_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="阶段ID，Snowflake BIGINT",
    )
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="任务版本ID")
    stage_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="阶段标识，版本内唯一")
    stage_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="阶段名称")
    mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="READ", comment="阶段模式：READ/PREPARE_WRITE/WRITE/VERIFY"
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="阶段顺序，从1递增")
    step_range_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="阶段内步骤索引列表JSON")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TaskRunStage(Base):
    """运行阶段实例：运行创建时从版本阶段复制快照，保存实际状态与产物引用。"""

    __tablename__ = "configuration_task_run_stage"
    __table_args__ = (
        UniqueConstraint("task_run_id", "stage_key", name="uk_ct_run_stage_run_key"),
        Index("idx_ct_run_stage_run_order", "task_run_id", "stage_order"),
        Index("idx_ct_run_stage_status", "status"),
    )

    run_stage_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="运行阶段ID，Snowflake BIGINT",
    )
    task_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="运行ID")
    stage_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="来源版本阶段ID")
    stage_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="阶段标识")
    stage_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="阶段名称")
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="READ", comment="阶段模式")
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="阶段顺序")
    step_range_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="阶段内步骤索引列表JSON")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", comment="阶段状态")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="阶段步骤结果JSON")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="错误码")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="错误消息")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="重试次数")
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="WRITE阶段审批人")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="审批时间")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="阶段开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="阶段结束时间")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class TaskArtifact(Base):
    """运行产物：截图、日志、报告与资源对象的多对一引用，只追加不覆盖。"""

    __tablename__ = "configuration_task_artifact"
    __table_args__ = (
        Index("idx_ct_artifact_run_stage", "task_run_id", "run_stage_id"),
        Index("idx_ct_artifact_type", "artifact_type"),
    )

    artifact_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="产物ID，Snowflake BIGINT",
    )
    task_run_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="运行ID")
    run_stage_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None, comment="运行阶段ID")
    artifact_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="产物类型：step_screenshot/failure_screenshot/execution_log/report",
    )
    step_key: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="关联步骤标识")
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="资源对象ID")
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="展示文件名")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="文件字节数")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="SHA-256")
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="产物说明")
    create_by: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="创建者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
