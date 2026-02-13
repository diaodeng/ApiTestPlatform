import os
import time
from typing import Optional

import psutil

from .enums import ModeEnum
from .utils import file_exists, is_linux, is_windows


class CgroupCPU:
    def __init__(self):
        self._last_usage_ns = None
        self._last_ts = None
        self.mode = self._detect_mode()

    # ---------- detect ----------
    def _detect_mode(self):
        if is_linux():
            if file_exists("/sys/fs/cgroup/cgroup.controllers"):
                return ModeEnum.CGROUP_2
            if file_exists("/sys/fs/cgroup/cpu"):
                return ModeEnum.CGROUP_1
            return ModeEnum.LINUX
        if is_windows():
            return ModeEnum.WINDOWS
        return "unknown"

    # ---------- CPU limit ----------

    def cpu_limit_cores(self) -> Optional[float]:
        if self.mode == ModeEnum.CGROUP_2:
            return self._cpu_limit_v2()
        if self.mode == ModeEnum.CGROUP_1:
            return self._cpu_limit_v1()
        return psutil.cpu_count(logical=True)

    def _cpu_limit_v2(self) -> Optional[float]:
        try:
            quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
            if quota == "max":
                return psutil.cpu_count()
            return int(quota) / int(period)
        except Exception:
            return psutil.cpu_count()

    def _cpu_limit_v1(self) -> Optional[float]:
        try:
            quota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            period = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            if quota <= 0:
                return psutil.cpu_count()
            return quota / period
        except Exception:
            return psutil.cpu_count()

    # ---------- usage ----------

    def _cpu_usage_ns(self) -> Optional[int]:
        if self.mode == ModeEnum.CGROUP_2:
            stat = open("/sys/fs/cgroup/cpu.stat").read()
            for line in stat.splitlines():
                if line.startswith("usage_usec"):
                    return int(line.split()[1]) * 1000
        elif self.mode == ModeEnum.CGROUP_1:
            return int(open("/sys/fs/cgroup/cpu/cpuacct.usage").read())
        return None

    def cpu_usage_percent(self, interval: float = 1.0) -> Optional[float]:
        """
        返回 CPU 使用率（相对于容器配额）
        """
        if self.mode in (ModeEnum.CGROUP_2, ModeEnum.CGROUP_1):
            usage1 = self._cpu_usage_ns()
            ts1 = time.time()

            time.sleep(interval)

            usage2 = self._cpu_usage_ns()
            ts2 = time.time()

            if usage1 is None or usage2 is None:
                return None

            delta_usage = usage2 - usage1
            delta_time = ts2 - ts1

            cores = self.cpu_limit_cores()
            if cores is None:
                cores = os.cpu_count() or 1

            # 使用率 = 实际使用时间 / (时间 * 可用核数)
            return (delta_usage / 1e9) / (delta_time * cores) * 100
        else:
            return psutil.cpu_percent(interval=interval)

    # ---------- health ----------

    def cpu_status(self) -> dict:
        cores = self.cpu_limit_cores()
        usage = self.cpu_usage_percent()

        # status = "SAFE"
        # if usage > 70:
        #     status = "WARN"
        # if usage > 85:
        #     status = "DANGER"

        return {
            "mode": self.mode,
            "cpu_limit_cores": round(cores, 2) if cores else None,
            "cpu_usage_percent": round(usage, 2),
            # "status": status,
        }


# ---------- demo ----------

if __name__ == "__main__":
    cpu = CgroupCPU()

    while True:
        data = cpu.cpu_status()
        os.system("clear")
        print("CGroup CPU Monitor")
        print("----------------------------")
        for k, v in data.items():
            print(f"{k:20}: {v}")
        time.sleep(1)
