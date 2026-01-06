import os
from typing import Dict

CGROUP_ROOT = "/sys/fs/cgroup"


def _read_int(path: str) -> int:
    try:
        with open(path, "r") as f:
            v = f.read().strip()
            if v == "max":
                return -1
            return int(v)
    except Exception:
        return 0


def _detect_cgroup_version() -> int:
    """
    return 1 or 2
    """
    if os.path.exists(os.path.join(CGROUP_ROOT, "cgroup.controllers")):
        return 2
    return 1


def collect_memory() -> Dict[str, float]:
    """
    返回单位：MB
    """
    version = _detect_cgroup_version()

    if version == 1:
        return _collect_v1()
    else:
        return _collect_v2()


def _collect_v1() -> Dict[str, float]:
    base = os.path.join(CGROUP_ROOT, "memory")

    usage = _read_int(f"{base}/memory.usage_in_bytes")
    limit = _read_int(f"{base}/memory.limit_in_bytes")

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
    can_usage = limit - hard_used

    available = max(limit - usage, 0) if limit > 0 else 0

    return {
        "cgroup_version": 1,
        "memory_limit_mb": limit / 1024 / 1024 if limit > 0 else -1,
        "memory_usage_mb": usage / 1024 / 1024,
        "memory_hard_usage_mb": hard_used / 1024 / 1024,
        "memory_cache_mb": cache / 1024 / 1024,
        "memory_rss_mb": rss / 1024 / 1024,
        "memory_available_mb": available / 1024 / 1024,
        "memory_actual_available_mb": can_usage / 1024 / 1024,
        "memory_pressure": usage / limit if limit > 0 else 0,
    }


def _collect_v2() -> Dict[str, float]:
    base = CGROUP_ROOT

    usage = _read_int(f"{base}/memory.current")
    limit = _read_int(f"{base}/memory.max")

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

    available = max(limit - usage, 0) if limit > 0 else 0

    return {
        "cgroup_version": 2,
        "memory_limit_mb": limit / 1024 / 1024 if limit > 0 else -1,
        "memory_usage_mb": usage / 1024 / 1024,
        "memory_cache_mb": cache / 1024 / 1024,
        "memory_rss_mb": rss / 1024 / 1024,
        "memory_available_mb": available / 1024 / 1024,
        "memory_pressure": usage / limit if limit > 0 else 0,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(collect_memory(), indent=2))
