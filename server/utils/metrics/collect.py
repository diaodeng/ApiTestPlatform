"""按固定低基数标签采集并推送进程、容器和任务指标。"""

from __future__ import annotations

import os
import threading
import time

import httpx
from loguru import logger

from config.env import MetricsConfig

from .container import CgroupCPU, MemoryCollector
from .process import CgroupMemoryCollector, ProcessCollector
from .task_memory import get_task_memory_observer


class PushDataToServer(threading.Thread):
    """将当前进程资源指标批量推送到 VictoriaMetrics/vmagent。"""

    def __init__(self, batch: int = 100, interval: int = 5, role: str | None = None):
        super().__init__(daemon=True)
        self.data_lines: list[str] = []
        self.batch = batch
        self.interval = interval
        self.current_time = time.time()
        self.vm_url = MetricsConfig.vm_url
        self.daemon = True
        self.stopped = False
        self.cpu_info = CgroupCPU()
        self.mem_info = MemoryCollector()
        self.process_info = ProcessCollector()
        self.cgroup_memory_info = CgroupMemoryCollector()
        self.role = role or os.environ.get("QTR_METRICS_ROLE", "api")
        self.extended_enabled = os.environ.get("QTR_METRICS_EXTENDED_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.task_observer = get_task_memory_observer(self.role)
        self.group = os.environ.get("SYM_GROUP", "stable")
        self.push_failures = 0
        if not self.vm_url:
            logger.warning(f"vm_url未配置，不推送统计数据: role={self.role}")

    def run(self):
        """循环采集并推送指标，采集或推送异常必须留下日志。"""
        logger.info(f"开始采集信息: role={self.role}")
        while self.vm_url and not self.stopped:
            try:
                self.push_machine_metrics()
                time.sleep(1)
            except Exception as exc:
                self.push_failures += 1
                logger.exception(f"指标采集失败: role={self.role}, failures={self.push_failures}, error={exc}")

    def stop(self):
        """停止采集线程并尽力发送剩余指标。"""
        self.stopped = True
        if self.data_lines:
            self._push()
        self.data_lines = []

    def _push(self):
        """批量发送指标，设置超时并记录失败原因。"""
        if not self.vm_url or not self.data_lines:
            return
        headers = {"Content-Type": "text/plain"}
        metrics_data = "\n".join(self.data_lines)
        try:
            response = httpx.post(
                self.vm_url,
                content=metrics_data,
                auth=(MetricsConfig.vm_user, MetricsConfig.vm_password),
                headers=headers,
                timeout=10.0,
                verify=False,
            )
            if response.status_code != 204:
                self.push_failures += 1
                logger.warning(
                    f"指标推送失败: role={self.role}, status={response.status_code}, "
                    f"samples={len(self.data_lines)}, bytes={len(metrics_data.encode('utf-8'))}, "
                    f"failures={self.push_failures}, response={response.text[:200]!r}"
                )
        except Exception as exc:
            self.push_failures += 1
            logger.exception(f"指标推送异常: role={self.role}, failures={self.push_failures}, error={exc}")

    @staticmethod
    def _escape_label_value(value: object) -> str:
        """按 Prometheus 文本协议转义标签值。"""
        return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    def _labels(self, sensor: str, extra: dict[str, str] | None = None) -> str:
        """构造固定低基数指标标签。"""
        labels = {
            "job": MetricsConfig.vm_job or "QTR",
            "instance": MetricsConfig.vm_instance or "TEST_ENV",
            "machine": MetricsConfig.vm_merchant or self.group,
            "sensor": sensor,
        }
        if self.extended_enabled:
            labels["role"] = self.role
        if extra:
            labels.update(extra)
        return ",".join(
            f'{key}="{self._escape_label_value(value)}"' for key, value in labels.items()
        )

    def _append_metric(self, name: str, value: int | float, labels: dict[str, str] | None = None):
        """追加一个纯数值 Prometheus 样本。"""
        timestamp = int(time.time() * 1000)
        label_str = self._labels(name, labels)
        self.data_lines.append(f"{name}{{{label_str}}} {value} {timestamp}")

    def push_machine_metrics(self):
        """采集旧版指标；扩展指标仅在显式启用时加入同一批次。"""
        data = {}
        data.update(self.cpu_info.cpu_status())
        data.update(self.mem_info.snapshot())
        for key, value in data.items():
            if key == "mode":
                continue
            self._append_metric(key, value)

        if self.extended_enabled:
            process_snapshot = self.process_info.snapshot()
            process_data = process_snapshot.as_dict()
            for key, value in process_data.items():
                self._append_metric(f"qtr_process_{key}", value)

            for key, value in self.cgroup_memory_info.snapshot().items():
                self._append_metric(key, value)

            for name, labels, value in self.task_observer.metrics():
                self._append_metric(name, value, labels)

        if len(self.data_lines) >= self.batch or time.time() - self.current_time >= self.interval:
            self._push()
            self.data_lines = []
            self.current_time = time.time()
