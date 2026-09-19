"""配置任务运行记录 ORM 实体。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from utils.snowflake import snowIdWorker


class ConfigurationTaskRun(Base):
    """配置任务运行实例：创建时冻结版本快照和输入资源，运行后只追加状态与结果。"""

    __tablename__ = "configuration_task_run"
    __table_args__ = (
        Index("idx_ct_run_task_time", "task_id", "started_at"),
        Index("idx_ct_run_agent_status", "agent_code", "status"),
    )

    task_run_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        nullable=False,
        unique=True,
        default=snowIdWorker.get_id,
        comment="运行ID，Snowflake BIGINT",
    )
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="任务ID")
    task_version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="执行版本ID")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="执行版本号")
    agent_code: Mapped[str] = mapped_column(String(128), nullable=False, comment="执行Agent编码")
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="触发类型")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
        comment="运行状态：PENDING/RUNNING/SUCCESS/FAILED/CANCELLED",
    )
    input_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="输入资源快照JSON")
    run_params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="运行参数快照JSON")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="Agent执行结果JSON")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="错误码")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="错误消息")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, comment="结束时间")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="执行时长毫秒")
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
