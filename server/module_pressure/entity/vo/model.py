from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScenarioCreateReq(BaseModel):
    """创建性能测试场景的请求模型。"""

    project_id: int = 0
    name: str
    engine: Literal["locust", "k6", "jmeter"] = "locust"
    base_url: str = ""
    dsl: dict[str, Any]
    csv_text: str | None = None
    remark: str | None = None


class ScenarioUpdateReq(BaseModel):
    """更新性能测试场景的请求模型。"""

    name: str | None = None
    engine: Literal["locust", "k6", "jmeter"] | None = None
    base_url: str | None = None
    dsl: dict[str, Any] | None = None
    csv_text: str | None = None
    remark: str | None = None


class RunCreateReq(BaseModel):
    """创建性能测试运行的请求模型。"""

    scenario_id: int
    users: int = Field(default=1, ge=1)
    spawn_rate: float = Field(default=1, gt=0)
    run_time: str | None = None
    target_qps: float | None = Field(default=None, gt=0)
    worker_mode: Literal["auto", "manual"] = "auto"
    worker_ids: list[str] = Field(default_factory=list)


class WorkerRegisterReq(BaseModel):
    """Worker 注册请求模型。"""

    worker_id: str
    host: str
    hostname: str | None = None
    cpu_cores: int = 1
    memory_mb: int = 1024
    max_users: int = 100
    engine_types: list[str] = Field(default_factory=lambda: ["locust"])
    labels: list[str] = Field(default_factory=list)


class WorkerHeartbeatReq(BaseModel):
    """Worker 心跳请求模型。"""

    worker_id: str
    run_id: int | None = None
    current_users: int = 0
    cpu_usage: float = 0
    memory_usage: float = 0
    rps: float = 0
    fail_rate: float = 0
    latency_ms: float = 0
    status: str | None = None


class RunCompareReq(BaseModel):
    """运行历史对比请求模型。"""

    run_ids: list[int]


class WorkerCapabilitySnapshot(BaseModel):
    """单次运行后的 Worker 能力样本。"""

    worker_id: str
    engine: str
    concurrency: int
    target_qps: float | None
    actual_qps: float
    avg_rt_ms: float
    error_rate: float
    success: bool
    timestamp: datetime
