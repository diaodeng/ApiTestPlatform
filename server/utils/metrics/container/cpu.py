import os
import time
from typing import Optional


class CgroupCPU:
    def __init__(self):
        self.version = self._detect_version()
        self.cpu_path = self._cpu_cgroup_path()
        self._last_usage_ns = None
        self._last_ts = None

    # ---------- detect ----------

    def _detect_version(self) -> int:
        if os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
            return 2
        return 1

    def _cpu_cgroup_path(self) -> str:
        if self.version == 2:
            return "/sys/fs/cgroup"
        return "/sys/fs/cgroup/cpu"

    # ---------- quota / cores ----------

    def cpu_limit_cores(self) -> Optional[float]:
        """
        返回容器可用 CPU 核数（可能是小数）
        None = unlimited
        """
        if self.version == 2:
            return self._cpu_limit_v2()
        return self._cpu_limit_v1()

    def _cpu_limit_v2(self) -> Optional[float]:
        path = os.path.join(self.cpu_path, "cpu.max")
        try:
            quota, period = open(path).read().strip().split()
            if quota == "max":
                return None
            return int(quota) / int(period)
        except Exception:
            return None

    def _cpu_limit_v1(self) -> Optional[float]:
        try:
            quota = int(open(f"{self.cpu_path}/cpu.cfs_quota_us").read())
            period = int(open(f"{self.cpu_path}/cpu.cfs_period_us").read())
            if quota <= 0:
                return None
            return quota / period
        except Exception:
            return None

    # ---------- usage ----------

    def _cpu_usage_ns(self) -> Optional[int]:
        if self.version == 2:
            stat = open(os.path.join(self.cpu_path, "cpu.stat")).read()
            for line in stat.splitlines():
                if line.startswith("usage_usec"):
                    return int(line.split()[1]) * 1000
        else:
            return int(open(f"{self.cpu_path}/cpuacct.usage").read())
        return None

    def cpu_usage_percent(self, interval: float = 1.0) -> Optional[float]:
        """
        返回 CPU 使用率（相对于容器配额）
        """
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

    # ---------- health ----------

    def cpu_status(self) -> dict:
        cores = self.cpu_limit_cores()
        usage = self.cpu_usage_percent()

        status = "SAFE"
        if usage is not None:
            if usage > 70:
                status = "WARN"
            if usage > 85:
                status = "DANGER"

        return {
            "cgroup_version": self.version,
            "cpu_limit_cores": cores,
            "cpu_usage_percent": round(usage, 2) if usage else None,
            "status": status,
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
