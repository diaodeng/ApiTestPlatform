"""进程级资源快照采集。"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass

import psutil


@dataclass(frozen=True)
class ProcessSnapshot:
    """记录当前 Python 进程的资源状态。"""

    pid: int
    rss_bytes: int
    vms_bytes: int
    uss_bytes: int
    threads: int
    children: int
    cpu_seconds_total: float
    start_time_seconds: float
    uptime_seconds: float
    open_files: int
    connections: int

    def as_dict(self) -> dict[str, int | float]:
        """转换为可推送的数值字段。"""
        values = asdict(self)
        values.pop("pid", None)
        return values


class ProcessCollector:
    """使用 psutil 采集当前进程资源，平台不支持的字段返回 0。"""

    def __init__(self, process: psutil.Process | None = None):
        self.process = process or psutil.Process(os.getpid())
        self._start_time = time.time()

    def snapshot(self) -> ProcessSnapshot:
        """读取一次当前进程资源快照。"""
        memory = self.process.memory_info()
        try:
            uss_bytes = int(self.process.memory_full_info().uss)
        except (AttributeError, OSError, psutil.Error):
            uss_bytes = 0

        try:
            open_files = len(self.process.open_files())
        except (OSError, psutil.Error):
            open_files = 0
        try:
            connection_reader = getattr(self.process, "net_connections", None)
            if connection_reader is None:
                connection_reader = getattr(self.process, "connections", None)
            connections = len(connection_reader()) if connection_reader else 0
        except (AttributeError, OSError, psutil.Error):
            connections = 0

        try:
            process_start = float(self.process.create_time())
        except (OSError, psutil.Error):
            process_start = self._start_time

        try:
            cpu_times = self.process.cpu_times()
            cpu_seconds_total = float(cpu_times.user + cpu_times.system)
        except (OSError, psutil.Error):
            cpu_seconds_total = 0.0

        try:
            children = len(self.process.children(recursive=True))
        except (OSError, psutil.Error):
            children = 0

        return ProcessSnapshot(
            pid=self.process.pid,
            rss_bytes=int(memory.rss),
            vms_bytes=int(memory.vms),
            uss_bytes=uss_bytes,
            threads=int(self.process.num_threads()),
            children=children,
            cpu_seconds_total=cpu_seconds_total,
            start_time_seconds=process_start,
            uptime_seconds=max(0.0, time.time() - process_start),
            open_files=open_files,
            connections=connections,
        )


class CgroupMemoryCollector:
    """采集 Linux cgroup v1/v2 内存字段，非 cgroup 环境返回空字典。"""

    V2_ROOT = "/sys/fs/cgroup"
    V1_ROOT = "/sys/fs/cgroup/memory"

    def snapshot(self) -> dict[str, int]:
        """读取 cgroup 内存使用、交换区和 OOM 计数。"""
        if os.path.exists(os.path.join(self.V2_ROOT, "cgroup.controllers")):
            return self._read_v2()
        if os.path.exists(self.V1_ROOT):
            return self._read_v1()
        return {}

    @staticmethod
    def _read_number(path: str) -> int | None:
        try:
            with open(path, encoding="utf-8") as file_obj:
                value = file_obj.read().strip()
            if value == "max":
                return None
            return int(value)
        except (OSError, ValueError):
            return None

    @classmethod
    def _read_stat(cls, path: str) -> dict[str, int]:
        values: dict[str, int] = {}
        try:
            with open(path, encoding="utf-8") as file_obj:
                for line in file_obj:
                    key, value = line.split(maxsplit=1)
                    values[key] = int(value)
        except (OSError, ValueError):
            return {}
        return values

    def _read_v2(self) -> dict[str, int]:
        root = self.V2_ROOT
        stat = self._read_stat(os.path.join(root, "memory.stat"))
        events = self._read_stat(os.path.join(root, "memory.events"))
        result = {
            "qtr_cgroup_memory_current_bytes": self._read_number(os.path.join(root, "memory.current")) or 0,
            "qtr_cgroup_memory_max_bytes": self._read_number(os.path.join(root, "memory.max")) or 0,
            "qtr_cgroup_memory_anon_bytes": stat.get("anon", 0),
            "qtr_cgroup_memory_file_bytes": stat.get("file", 0),
            "qtr_cgroup_memory_kernel_bytes": stat.get("kernel", 0),
            "qtr_cgroup_memory_slab_bytes": stat.get("slab", 0),
            "qtr_cgroup_memory_swap_bytes": stat.get("swap", 0),
            "qtr_cgroup_memory_events_high_total": events.get("high", 0),
            "qtr_cgroup_memory_events_oom_total": events.get("oom", 0),
            "qtr_cgroup_memory_events_oom_kill_total": events.get("oom_kill", 0),
        }
        return result

    def _read_v1(self) -> dict[str, int]:
        root = self.V1_ROOT
        stat = self._read_stat(os.path.join(root, "memory.stat"))
        return {
            "qtr_cgroup_memory_current_bytes": self._read_number(os.path.join(root, "memory.usage_in_bytes")) or 0,
            "qtr_cgroup_memory_max_bytes": self._read_number(os.path.join(root, "memory.limit_in_bytes")) or 0,
            "qtr_cgroup_memory_anon_bytes": stat.get("rss", 0),
            "qtr_cgroup_memory_file_bytes": stat.get("cache", 0),
            "qtr_cgroup_memory_kernel_bytes": stat.get("slab", 0),
            "qtr_cgroup_memory_slab_bytes": stat.get("slab", 0),
            "qtr_cgroup_memory_swap_bytes": 0,
            "qtr_cgroup_memory_events_high_total": 0,
            "qtr_cgroup_memory_events_oom_total": 0,
            "qtr_cgroup_memory_events_oom_kill_total": 0,
        }
