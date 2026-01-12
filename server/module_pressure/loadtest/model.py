from pydantic import BaseModel
import datetime

class WorkerInfo(BaseModel):
    worker_id: str
    hostname: str
    queues: list[str]
    engine_types: list[str]  # locust / k6 / jmeter


class WorkerCapabilitySnapshot(BaseModel):
    worker_id: str
    engine: str               # locust
    concurrency: int          # 实际并发
    target_qps: float | None
    actual_qps: float
    avg_rt_ms: float
    error_rate: float
    success: bool
    timestamp: datetime


class WorkerCapabilityModel(BaseModel):
    worker_id: str
    engine: str

    max_stable_concurrency: int
    max_stable_qps: float

    avg_rt_ms: float
    error_rate: float

    confidence: float         # 样本可信度 0~1
    last_updated: datetime


class LoadTestResult(BaseModel):
    worker_id: str
    engine: str
    concurrency: int
    duration: int

    total_requests: int
    success_requests: int
    fail_requests: int

    avg_rt_ms: float
    actual_qps: float


class LoadTestPlan(BaseModel):
    engine: str
    target_qps: float
    duration: int
