from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.common_do import BaseModel
from config.database import Base
from module_pressure.enums import PressureRunStatus


class PressureScenario(Base, BaseModel):
    """性能测试场景，保存平台编辑后的 DSL 和参数化 CSV 数据。"""

    __tablename__ = "pressure_scenario"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="项目ID")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="场景名称")
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="locust", comment="执行引擎")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="", comment="被测服务地址")
    dsl: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="场景DSL")
    csv_text: Mapped[str | None] = mapped_column(Text, nullable=True, comment="参数化CSV文本")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")


class PressureRun(Base, BaseModel):
    """性能测试运行记录，运行时独立生成脚本、数据和报告产物。"""

    __tablename__ = "pressure_run"

    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="项目ID")
    scenario_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("pressure_scenario.id"),
        nullable=True,
        comment="场景ID",
    )
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="locust", comment="执行引擎")
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="并发用户数")
    spawn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1, comment="启动速率")
    run_time: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="执行时长，例如 5m")
    target_qps: Mapped[float | None] = mapped_column(Float, nullable=True, comment="目标QPS")
    worker_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="auto", comment="auto/manual")
    requested_worker_ids: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="手动选择的Worker")
    allocated_worker_ids: Mapped[list | None] = mapped_column(JSON, nullable=True, comment="实际分配的Worker")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PressureRunStatus.PENDING.value,
        comment="运行状态",
    )
    master_host: Mapped[str] = mapped_column(String(128), nullable=False, default="127.0.0.1", comment="Master地址")
    master_web_port: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Locust Web端口")
    master_bind_port: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Locust Master端口")
    master_pid: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Master进程ID")
    artifact_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="运行产物目录")
    script_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="Locust脚本路径")
    csv_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="CSV数据路径")
    report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="HTML报告路径")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="报告摘要")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")


class PressureWorker(Base, BaseModel):
    """压测执行节点注册表，平台通过心跳判断可用性和占用状态。"""

    __tablename__ = "pressure_worker"

    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True, comment="Worker标识")
    host: Mapped[str] = mapped_column(String(256), nullable=False, comment="Worker主机或连接地址")
    hostname: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="主机名")
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="CPU核数")
    memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=1024, comment="内存MB")
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="理论最大用户数")
    current_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前用户数")
    engine_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="支持的引擎")
    labels: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="调度标签")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle", comment="idle/busy/unhealthy")
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="CPU使用率")
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="内存使用率")
    rps: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="当前RPS")
    fail_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="失败率")
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="平均响应时间")
    busy_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="占用运行ID")
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最后心跳时间")


class PressureWorkerHeartbeat(Base, BaseModel):
    """Worker 心跳历史，用于故障回放和能力画像计算。"""

    __tablename__ = "pressure_worker_heartbeat"

    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="Worker标识")
    run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="运行ID")
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="CPU使用率")
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="内存使用率")
    current_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前用户数")
    rps: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="当前RPS")
    fail_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="失败率")
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="平均响应时间")
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="记录时间")


class PressureWorkerCapacityProfile(Base, BaseModel):
    """Worker 历史能力画像，调度时用于自动选择执行节点。"""

    __tablename__ = "pressure_worker_capacity_profile"

    worker_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="Worker标识")
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="locust", comment="执行引擎")
    stable_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="稳定用户数")
    max_qps: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="历史最大稳定QPS")
    avg_rt_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="平均响应时间")
    error_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="错误率")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="画像可信度")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="样本数")
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="更新时间")
