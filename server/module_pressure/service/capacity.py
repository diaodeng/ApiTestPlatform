from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from module_pressure.entity.do.models import PressureWorker, PressureWorkerCapacityProfile


class ResourceNotEnoughError(RuntimeError):
    """可用 Worker 无法满足本次压测容量时抛出。"""


@dataclass
class WorkerAllocation:
    """单个 Worker 的分配结果。"""

    worker_id: str
    users: int


def estimate_required_users(
    *,
    target_qps: float | None,
    avg_rt_ms: float | None,
    configured_users: int,
    safety_factor: float = 1.3,
) -> int:
    """根据 Little's Law 估算需要的并发用户数，缺少 QPS/RT 时使用用户配置。"""
    if not target_qps or not avg_rt_ms:
        return max(configured_users, 1)
    users = target_qps * (avg_rt_ms / 1000.0) * safety_factor
    return max(math.ceil(users), configured_users, 1)


def worker_free_capacity(worker: PressureWorker, profile: PressureWorkerCapacityProfile | None = None) -> int:
    """计算 Worker 当前可用容量，结合心跳压力和历史稳定用户数。"""
    if worker.status != "idle":
        return 0
    if not worker.last_heartbeat:
        return 0

    heartbeat_age = (datetime.now() - worker.last_heartbeat).total_seconds()
    if heartbeat_age > 15:
        return 0

    stable_users = profile.stable_users if profile and profile.stable_users > 0 else worker.max_users
    free_users = max(stable_users - worker.current_users, 0)
    if worker.cpu_usage >= 0.85:
        free_users *= 0.5
    if worker.memory_usage >= 0.9:
        free_users = 0
    if worker.fail_rate >= 0.2:
        free_users *= 0.5
    return int(max(free_users * 0.8, 0))


def worker_score(worker: PressureWorker, profile: PressureWorkerCapacityProfile | None = None) -> float:
    """计算 Worker 调度分数，容量越高、失败率越低、延迟越低则分数越高。"""
    capacity = worker_free_capacity(worker, profile)
    latency_ms = profile.avg_rt_ms if profile and profile.avg_rt_ms > 0 else worker.latency_ms
    latency_penalty = max(1.0, latency_ms / 100.0)
    error_rate = profile.error_rate if profile and profile.sample_count > 0 else worker.fail_rate
    confidence = profile.confidence if profile else 0.5
    return capacity * max(0.1, 1.0 - error_rate) * max(0.5, confidence) / latency_penalty


def select_workers(
    workers: list[PressureWorker],
    required_users: int,
    profile_getter,
) -> list[WorkerAllocation]:
    """按容量评分选择 Worker，返回每台 Worker 分配的用户数。"""
    selected: list[WorkerAllocation] = []
    remaining = required_users
    scored_workers = sorted(
        workers,
        key=lambda item: worker_score(item, profile_getter(item.worker_id)),
        reverse=True,
    )

    for worker in scored_workers:
        capacity = worker_free_capacity(worker, profile_getter(worker.worker_id))
        if capacity <= 0:
            continue
        users = min(capacity, remaining)
        selected.append(WorkerAllocation(worker_id=worker.worker_id, users=users))
        remaining -= users
        if remaining <= 0:
            return selected

    raise ResourceNotEnoughError(f"可用 Worker 容量不足，还缺少 {remaining} 个用户容量")


def update_profile_sample(
    profile: PressureWorkerCapacityProfile | None,
    *,
    users: int,
    qps: float,
    avg_rt_ms: float,
    error_rate: float,
) -> dict:
    """根据一次运行样本计算新的能力画像字段。"""
    sample_count = (profile.sample_count if profile else 0) + 1
    old_weight = max(sample_count - 1, 0)
    old_stable = profile.stable_users if profile else 0
    old_qps = profile.max_qps if profile else 0
    old_rt = profile.avg_rt_ms if profile else 0
    old_error = profile.error_rate if profile else 0

    successful_sample = error_rate < 0.05
    stable_users = max(old_stable, users) if successful_sample else old_stable
    max_qps = max(old_qps, qps) if successful_sample else old_qps
    avg_rt = ((old_rt * old_weight) + avg_rt_ms) / sample_count
    avg_error = ((old_error * old_weight) + error_rate) / sample_count
    confidence = min(1.0, sample_count / 10.0)

    return {
        "stable_users": stable_users,
        "max_qps": max_qps,
        "avg_rt_ms": avg_rt,
        "error_rate": avg_error,
        "confidence": confidence,
        "sample_count": sample_count,
    }
