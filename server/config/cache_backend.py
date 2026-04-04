from __future__ import annotations

import fnmatch
import time
from collections import Counter
from datetime import timedelta
from threading import RLock
from typing import Any


class MemoryRedis:
    """一个尽量兼容 redis.asyncio 常用接口的内存缓存实现。"""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._command_stats: Counter[str] = Counter()
        self._lock = RLock()

    def _record(self, command: str) -> None:
        self._command_stats[command] += 1

    @staticmethod
    def _stringify(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _ttl_seconds(ex: int | float | timedelta | None) -> float | None:
        if ex is None:
            return None
        if isinstance(ex, timedelta):
            return max(ex.total_seconds(), 0)
        return max(float(ex), 0)

    def _purge_expired_key(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return
        if expires_at <= time.time():
            self._store.pop(key, None)
            self._expires_at.pop(key, None)

    def _purge_expired(self) -> None:
        for key in list(self._store.keys()):
            self._purge_expired_key(key)

    async def ping(self) -> bool:
        self._record("ping")
        return True

    async def close(self) -> None:
        self._record("close")

    async def get(self, key: str) -> str | None:
        self._record("get")
        with self._lock:
            self._purge_expired_key(key)
            return self._store.get(key)

    async def set(self, key: str, value: Any, ex: int | float | timedelta | None = None) -> bool:
        self._record("set")
        with self._lock:
            self._store[key] = self._stringify(value) or ""
            ttl_seconds = self._ttl_seconds(ex)
            if ttl_seconds is None:
                self._expires_at.pop(key, None)
            else:
                self._expires_at[key] = time.time() + ttl_seconds
        return True

    async def setnx(self, key: str, value: Any) -> bool:
        self._record("setnx")
        with self._lock:
            self._purge_expired_key(key)
            if key in self._store:
                return False
            self._store[key] = self._stringify(value) or ""
            self._expires_at.pop(key, None)
            return True

    async def sernx(self, key: str, value: Any) -> bool:
        """兼容项目里现有的 `sernx` 拼写。"""
        self._record("sernx")
        return await self.setnx(key, value)

    async def delete(self, *keys: str) -> int:
        self._record("delete")
        removed = 0
        with self._lock:
            for key in keys:
                self._purge_expired_key(key)
                existed = key in self._store
                self._store.pop(key, None)
                self._expires_at.pop(key, None)
                if existed:
                    removed += 1
        return removed

    async def expire(self, key: str, seconds: int | float | timedelta) -> bool:
        self._record("expire")
        with self._lock:
            self._purge_expired_key(key)
            if key not in self._store:
                return False
            ttl_seconds = self._ttl_seconds(seconds)
            if ttl_seconds is None:
                self._expires_at.pop(key, None)
            else:
                self._expires_at[key] = time.time() + ttl_seconds
            return True

    async def ttl(self, key: str) -> int:
        self._record("ttl")
        with self._lock:
            self._purge_expired_key(key)
            if key not in self._store:
                return -2
            expires_at = self._expires_at.get(key)
            if expires_at is None:
                return -1
            ttl = int(expires_at - time.time())
            if ttl <= 0:
                self._store.pop(key, None)
                self._expires_at.pop(key, None)
                return -2
            return ttl

    async def scan(self, cursor: int | str = 0, match: str | None = None, count: int | None = None) -> tuple[int, list[str]]:
        self._record("scan")
        del cursor, count
        with self._lock:
            self._purge_expired()
            keys = list(self._store.keys())
            if match:
                keys = [key for key in keys if fnmatch.fnmatch(key, match)]
            return 0, keys

    async def dbsize(self) -> int:
        self._record("dbsize")
        with self._lock:
            self._purge_expired()
            return len(self._store)

    async def info(self, section: str | None = None) -> dict[str, Any]:
        self._record("info")
        with self._lock:
            self._purge_expired()
            if section == "commandstats":
                return {
                    f"cmdstat_{command}": {"calls": calls}
                    for command, calls in sorted(self._command_stats.items())
                }
            return {
                "redis_mode": "memory",
                "redis_version": "memory-backend",
                "connected_clients": 1,
                "used_memory_human": "0B",
                "db_size": len(self._store),
            }
