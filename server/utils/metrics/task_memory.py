"""任务级内存观测与结构化诊断日志。"""

from __future__ import annotations

import gc
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .process import ProcessCollector, ProcessSnapshot


@dataclass
class TaskObservation:
    """保存任务开始时的进程快照。"""

    started_at: float
    before: ProcessSnapshot


class TaskMemoryObserver:
    """记录任务前后内存，并提供低基数的聚合指标。"""

    def __init__(self, role: str = "api", process_collector: ProcessCollector | None = None):
        self.role = role
        self.process_collector = process_collector or ProcessCollector()
        self._lock = threading.Lock()
        self._active = 0
        self._completed: dict[tuple[str, str, str, str, str], int] = {}
        self._last: dict[tuple[str, str, str, str, str], dict[str, int | float]] = {}

    @staticmethod
    def _labels(context: dict[str, Any]) -> tuple[str, str, str, str, str]:
        """将任务上下文归一化为低基数标签。"""
        return (
            str(context.get("owner_type") or "unknown"),
            str(context.get("task_family") or "unknown"),
            str(context.get("queue_name") or "unknown"),
            str(context.get("trigger_type") or "unknown"),
            str(context.get("status") or "running"),
        )

    def start(self, context: dict[str, Any]) -> TaskObservation:
        """记录任务开始快照并输出诊断日志。"""
        observation = TaskObservation(time.time(), self.process_collector.snapshot())
        with self._lock:
            self._active += 1
        logger.info(self._format_log("task_memory_start", context, observation.before))
        return observation

    def finish(self, context: dict[str, Any], observation: TaskObservation, status: str) -> dict[str, int | float]:
        """记录任务结束快照、聚合指标和结束日志。"""
        after = self.process_collector.snapshot()
        gc.collect()
        after_gc = self.process_collector.snapshot()
        duration_ms = round((time.time() - observation.started_at) * 1000, 2)
        values = {
            "duration_ms": duration_ms,
            "memory_before_bytes": observation.before.rss_bytes,
            "memory_after_bytes": after.rss_bytes,
            "memory_delta_bytes": after.rss_bytes - observation.before.rss_bytes,
            "memory_after_gc_bytes": after_gc.rss_bytes,
            "uss_before_bytes": observation.before.uss_bytes,
            "uss_after_bytes": after.uss_bytes,
            "uss_delta_bytes": after.uss_bytes - observation.before.uss_bytes,
            "threads_before": observation.before.threads,
            "threads_after": after.threads,
            "children_before": observation.before.children,
            "children_after": after.children,
        }
        context = {**context, "status": status}
        labels = self._labels(context)
        with self._lock:
            self._active = max(0, self._active - 1)
            self._completed[labels] = self._completed.get(labels, 0) + 1
            self._last[labels] = values
        logger.info(self._format_log("task_memory_finish", context, after, values))
        return values

    def metrics(self) -> list[tuple[str, dict[str, str], int | float]]:
        """返回适合 VM 推送的低基数数值指标。"""
        with self._lock:
            active = self._active
            completed = dict(self._completed)
            latest = dict(self._last)
        result: list[tuple[str, dict[str, str], int | float]] = [
            ("qtr_task_active", {"role": self.role}, active),
        ]
        for labels, count in completed.items():
            owner_type, task_family, queue_name, trigger_type, status = labels
            metric_labels = {
                "role": self.role,
                "owner_type": owner_type,
                "task_family": task_family,
                "queue_name": queue_name,
                "trigger_type": trigger_type,
                "status": status,
            }
            result.append(("qtr_task_completed_total", metric_labels, count))
            values = latest.get(labels, {})
            for key, metric_name in (
                ("duration_ms", "qtr_task_duration_ms"),
                ("memory_before_bytes", "qtr_task_memory_before_bytes"),
                ("memory_after_bytes", "qtr_task_memory_after_bytes"),
                ("memory_delta_bytes", "qtr_task_memory_delta_bytes"),
                ("memory_after_gc_bytes", "qtr_task_memory_after_gc_bytes"),
                ("threads_after", "qtr_task_threads"),
                ("children_after", "qtr_task_children"),
            ):
                if key in values:
                    result.append((metric_name, metric_labels, values[key]))
        return result

    def _format_log(
        self,
        event: str,
        context: dict[str, Any],
        snapshot: ProcessSnapshot,
        values: dict[str, int | float] | None = None,
    ) -> str:
        """生成不包含任务正文的单行诊断日志。"""
        values = values or {}
        fields = {
            "event": event,
            "role": self.role,
            "pid": snapshot.pid,
            "task_id": context.get("task_id", "-"),
            "celery_task_id": context.get("celery_task_id", "-"),
            "trace_id": context.get("trace_id", "-"),
            "task_key": context.get("task_key", "-"),
            "queue_name": context.get("queue_name", "-"),
            "owner_type": context.get("owner_type", "-"),
            "trigger_type": context.get("trigger_type", "-"),
            "status": context.get("status", "running"),
            "rss_bytes": snapshot.rss_bytes,
            "uss_bytes": snapshot.uss_bytes,
            "threads": snapshot.threads,
            "children": snapshot.children,
        }
        fields.update(values)
        return " ".join(f"{key}={str(value).replace(' ', '_')}" for key, value in fields.items())


_default_observer = TaskMemoryObserver(role=os.environ.get("QTR_METRICS_ROLE", "api"))


def get_task_memory_observer(role: str | None = None) -> TaskMemoryObserver:
    """返回当前进程共享的任务观测器。

    :param role: 可选角色覆盖。业务代码不应传值——角色由部署环境
        （supervisord 的 QTR_METRICS_ROLE）决定；只有测试或确需显式
        切换角色的采集组件才传入。历史上有调用方硬编码传 "api"，
        导致 celery worker 进程的任务日志/指标被错误标记为 role=api，
        污染内存归因，已全部移除。
    """
    if role:
        _default_observer.role = role
    return _default_observer
