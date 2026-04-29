import os
from typing import Dict
from typing import Optional

import psutil
from .utils import is_linux,is_windows,file_exists
from .enums import ModeEnum

CGROUP_ROOT = "/sys/fs/cgroup"


class MemoryCollector:
    def __init__(self):
        self.mode = self._detect_mode()

    def _detect_mode(self):
        if is_linux():
            if file_exists("/sys/fs/cgroup/cgroup.controllers"):
                return ModeEnum.CGROUP_2
            if file_exists("/sys/fs/cgroup/memory"):
                return ModeEnum.CGROUP_1
            return ModeEnum.LINUX
        if is_windows():
            return ModeEnum.WINDOWS
        return "unknown"

    # ---------- limits ----------

    def memory_limit_bytes(self) -> Optional[int]:
        if self.mode == ModeEnum.CGROUP_2:
            return self._mem_limit_v2()
        if self.mode == ModeEnum.CGROUP_1:
            return self._mem_limit_v1()
        return psutil.virtual_memory().total

    def _mem_limit_v2(self) -> Optional[int]:
        try:
            val = open("/sys/fs/cgroup/memory.max").read().strip()
            if val == "max":
                return psutil.virtual_memory().total
            return int(val)
        except Exception:
            return psutil.virtual_memory().total

    def _mem_limit_v1(self) -> Optional[int]:
        try:
            return int(open("/sys/fs/cgroup/memory/memory.limit_in_bytes").read())
        except Exception:
            return psutil.virtual_memory().total

    # ---------- usage ----------

    def memory_used_bytes(self) -> int:
        """
        统一语义：主要工作集（RSS）
        """
        if self.mode == ModeEnum.CGROUP_2:
            return self._mem_used_v2_bytes()
        elif self.mode == ModeEnum.CGROUP_1:
            return self._mem_used_v1_bytes()
        else:
            return psutil.Process(os.getpid()).memory_info().rss

    def _mem_used_v2_bytes(self) -> Optional[int]:
        base = CGROUP_ROOT

        # usage = 0
        # try:
        #     with open(f"{base}/memory.current", "r") as f:
        #         v = f.read().strip()
        #         if v == "max":
        #             usage = -1
        #         usage = int(v)
        # except Exception:
        #     pass

        stat = {}
        try:
            with open(f"{base}/memory.stat") as f:
                for line in f:
                    k, v = line.split()
                    stat[k] = int(v)
        except Exception:
            pass

        cache = stat.get("file", 0)
        rss = stat.get("anon", 0)

        return rss

    def _mem_used_v1_bytes(self) -> Optional[int]:
        base = os.path.join(CGROUP_ROOT, "memory")
        stat = {}
        try:
            with open(f"{base}/memory.stat") as f:
                for line in f:
                    k, v = line.split()
                    stat[k] = int(v)
        except Exception:
            pass

        cache = stat.get("cache", 0)
        rss = stat.get("rss", 0)
        slab_unrec = stat.get("slab_unreclaimable", 0)
        hard_used = rss + slab_unrec

        return hard_used

    def memory_available_bytes(self) -> int:
        limit = self.memory_limit_bytes()
        used = self.memory_used_bytes()
        return max(0, limit - used)

    # ---------- summary ----------

    def snapshot(self) -> dict:
        limit = self.memory_limit_bytes()
        used = self.memory_used_bytes()
        avail = max(0, limit - used)

        pressure = used / limit * 100 if limit else 0

        # status = "SAFE"
        # if pressure > 70:
        #     status = "WARN"
        # if pressure > 85:
        #     status = "DANGER"

        return {
            "mode": self.mode,
            "memory_limit_mb": round(limit / 1024 / 1024),
            "memory_used_mb": round(used / 1024 / 1024),
            # "memory_cache_mb": cache / 1024 / 1024,
            "memory_actual_available_mb": round(avail / 1024 / 1024),
            "memory_pressure": round(pressure, 2),
            # "status": status,
        }


if __name__ == "__main__":
    import json
    print(json.dumps(MemoryCollector.snapshot(), indent=2))
