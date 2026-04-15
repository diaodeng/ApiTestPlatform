from datetime import datetime

from sqlalchemy import (
    BIGINT,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from config.database import Base
from config.sqlalchemy_types import long_text_type


class CeleryPeriodicTask(Base):
    """
    Celery 原生周期任务配置表。
    """

    __tablename__ = "celery_periodic_task"
    __table_args__ = (
        UniqueConstraint("owner_type", "task_name", name="uq_celery_task_owner_name"),
        Index("idx_celery_task_owner_enabled", "owner_type", "enabled"),
        Index("idx_celery_task_owner_user", "owner_type", "owner_user_id"),
        Index("idx_celery_task_owner_dept", "owner_type", "owner_dept_id"),
    )

    task_id = Column(Integer, primary_key=True, autoincrement=True, comment="任务主键")
    owner_type = Column(String(16), nullable=False, default="sys", comment="任务归属类型：sys/qtr")
    owner_user_id = Column(BIGINT, nullable=True, comment="归属用户ID")
    owner_dept_id = Column(Integer, nullable=True, comment="归属部门ID")

    task_name = Column(String(128), nullable=False, comment="任务显示名称")
    task_key = Column(String(255), nullable=False, comment="任务注册键")
    queue_name = Column(String(64), nullable=False, default="celery", comment="Celery 队列")

    schedule_type = Column(String(16), nullable=False, default="crontab", comment="调度类型")
    cron_expression = Column(String(128), nullable=True, comment="Cron 表达式")
    interval_every = Column(Integer, nullable=True, comment="间隔调度步长")
    interval_period = Column(String(16), nullable=True, comment="间隔调度单位")
    one_off_eta = Column(DateTime, nullable=True, comment="单次任务触发时间")
    one_off_consumed = Column(Boolean, nullable=False, default=False, comment="单次任务是否已触发")

    task_args_json = Column(long_text_type(), nullable=False, default="[]", comment="JSON 位置参数")
    task_kwargs_json = Column(long_text_type(), nullable=False, default="{}", comment="JSON 关键字参数")

    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    allow_concurrent = Column(Boolean, nullable=False, default=False, comment="是否允许并发")
    lock_ttl_seconds = Column(Integer, nullable=False, default=3600, comment="并发互斥锁TTL")
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai", comment="调度时区")

    last_status = Column(String(16), nullable=True, comment="最近一次执行状态")
    last_message = Column(String(500), nullable=True, comment="最近一次执行消息")
    last_run_at = Column(DateTime, nullable=True, comment="最近一次开始执行时间")
    last_duration_ms = Column(Integer, nullable=True, comment="最近一次耗时毫秒")
    run_count = Column(Integer, nullable=False, default=0, comment="累计执行次数")

    create_by = Column(String(64), nullable=True, default="", comment="创建人")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_by = Column(String(64), nullable=True, default="", comment="更新人")
    update_time = Column(DateTime, nullable=False, default=datetime.now, comment="更新时间")
    remark = Column(String(500), nullable=True, default="", comment="备注")


class CeleryTaskExecutionLog(Base):
    """
    Celery 任务执行日志表。
    """

    __tablename__ = "celery_task_execution_log"
    __table_args__ = (
        Index("idx_celery_log_owner_time", "owner_type", "create_time"),
        Index("idx_celery_log_task_time", "task_id", "create_time"),
        Index("idx_celery_log_status", "status"),
    )

    log_id = Column(Integer, primary_key=True, autoincrement=True, comment="日志主键")
    task_id = Column(Integer, nullable=False, comment="任务ID")
    owner_type = Column(String(16), nullable=False, default="sys", comment="任务归属类型：sys/qtr")

    task_name = Column(String(128), nullable=False, comment="任务显示名称")
    task_key = Column(String(255), nullable=False, comment="任务注册键")
    queue_name = Column(String(64), nullable=False, default="celery", comment="队列名")

    trigger_type = Column(String(16), nullable=False, default="scheduler", comment="触发方式")
    celery_task_id = Column(String(64), nullable=True, comment="Celery Task ID")
    schedule_desc = Column(String(255), nullable=True, comment="触发时的调度描述")

    status = Column(String(16), nullable=False, default="success", comment="执行状态")
    message = Column(String(500), nullable=True, default="", comment="执行摘要")
    exception_info = Column(long_text_type(), nullable=True, default="", comment="异常信息")
    args_json = Column(long_text_type(), nullable=False, default="[]", comment="位置参数快照")
    kwargs_json = Column(long_text_type(), nullable=False, default="{}", comment="关键字参数快照")

    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    finished_at = Column(DateTime, nullable=True, comment="结束执行时间")
    duration_ms = Column(Integer, nullable=True, comment="执行耗时毫秒")
    create_time = Column(DateTime, nullable=False, default=datetime.now, comment="日志创建时间")
