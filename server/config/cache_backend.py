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
        self._lists: dict[str, list[str]] = {}
        self._hashes: dict[str, dict[str, str]] = {}
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
            self._drop_key(key)

    def _drop_key(self, key: str) -> None:
        """删除指定键的所有缓存态。"""
        self._store.pop(key, None)
        self._lists.pop(key, None)
        self._hashes.pop(key, None)
        self._expires_at.pop(key, None)

    def _purge_expired(self) -> None:
        for key in {*self._store.keys(), *self._lists.keys(), *self._hashes.keys()}:
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

    async def set(
        self,
        key: str,
        value: Any,
        ex: int | float | timedelta | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        self._record("set")
        with self._lock:
            self._purge_expired_key(key)
            key_exists = key in self._store or key in self._lists or key in self._hashes
            if nx and key_exists:
                return None
            if xx and not key_exists:
                return None
            self._drop_key(key)
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
                existed = key in self._store or key in self._lists or key in self._hashes
                self._drop_key(key)
                if existed:
                    removed += 1
        return removed

    async def exists(self, *keys: str) -> int:
        self._record("exists")
        with self._lock:
            count = 0
            for key in keys:
                self._purge_expired_key(key)
                if key in self._store or key in self._lists or key in self._hashes:
                    count += 1
            return count

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

    async def scan(
        self,
        cursor: int | str = 0,
        match: str | None = None,
        count: int | None = None,
    ) -> tuple[int, list[str]]:
        self._record("scan")
        del cursor, count
        with self._lock:
            self._purge_expired()
            keys = list({*self._store.keys(), *self._lists.keys(), *self._hashes.keys()})
            if match:
                keys = [key for key in keys if fnmatch.fnmatch(key, match)]
            return 0, keys

    async def rpush(self, key: str, *values: Any) -> int:
        self._record("rpush")
        with self._lock:
            self._purge_expired_key(key)
            if key in self._store:
                self._drop_key(key)
            queue = self._lists.setdefault(key, [])
            for value in values:
                queue.append(self._stringify(value) or "")
            return len(queue)

    async def lpush(self, key: str, *values: Any) -> int:
        self._record("lpush")
        with self._lock:
            self._purge_expired_key(key)
            if key in self._store:
                self._drop_key(key)
            queue = self._lists.setdefault(key, [])
            for value in values:
                queue.insert(0, self._stringify(value) or "")
            return len(queue)

    async def lpop(self, key: str) -> str | None:
        self._record("lpop")
        with self._lock:
            self._purge_expired_key(key)
            queue = self._lists.get(key)
            if not queue:
                return None
            value = queue.pop(0)
            if not queue:
                self._lists.pop(key, None)
                self._expires_at.pop(key, None)
            return value

    async def lindex(self, key: str, index: int) -> str | None:
        self._record("lindex")
        with self._lock:
            self._purge_expired_key(key)
            queue = self._lists.get(key) or []
            try:
                return queue[index]
            except Exception:
                return None

    async def llen(self, key: str) -> int:
        self._record("llen")
        with self._lock:
            self._purge_expired_key(key)
            return len(self._lists.get(key) or [])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        self._record("lrange")
        with self._lock:
            self._purge_expired_key(key)
            queue = list(self._lists.get(key) or [])
            if end == -1:
                end = len(queue) - 1
            if start < 0:
                start = max(len(queue) + start, 0)
            if end < 0:
                end = len(queue) + end
            if end < start:
                return []
            return queue[start : end + 1]

    async def lrem(self, key: str, count: int, value: Any) -> int:
        self._record("lrem")
        with self._lock:
            self._purge_expired_key(key)
            queue = self._lists.get(key)
            if not queue:
                return 0
            target = self._stringify(value) or ""
            removed = 0
            if count == 0:
                new_queue = [item for item in queue if item != target]
                removed = len(queue) - len(new_queue)
                if new_queue:
                    self._lists[key] = new_queue
                else:
                    self._lists.pop(key, None)
                    self._expires_at.pop(key, None)
                return removed
            if count > 0:
                new_queue: list[str] = []
                for item in queue:
                    if item == target and removed < count:
                        removed += 1
                        continue
                    new_queue.append(item)
            else:
                limit = abs(count)
                reversed_queue = list(reversed(queue))
                new_queue = []
                for item in reversed_queue:
                    if item == target and removed < limit:
                        removed += 1
                        continue
                    new_queue.append(item)
                new_queue.reverse()
            if new_queue:
                self._lists[key] = new_queue
            else:
                self._lists.pop(key, None)
                self._expires_at.pop(key, None)
            return removed

    async def hset(
        self,
        key: str,
        field: str | None = None,
        value: Any | None = None,
        mapping: dict | None = None,
    ) -> int:
        self._record("hset")
        with self._lock:
            self._purge_expired_key(key)
            if key in self._store:
                self._drop_key(key)
            hash_value = self._hashes.setdefault(key, {})
            added = 0
            if mapping:
                for map_field, map_value in mapping.items():
                    if map_field not in hash_value:
                        added += 1
                    hash_value[str(map_field)] = self._stringify(map_value) or ""
            if field is not None:
                if field not in hash_value:
                    added += 1
                hash_value[str(field)] = self._stringify(value) or ""
            return added

    async def hgetall(self, key: str) -> dict[str, str]:
        self._record("hgetall")
        with self._lock:
            self._purge_expired_key(key)
            return dict(self._hashes.get(key) or {})

    async def hdel(self, key: str, *fields: str) -> int:
        self._record("hdel")
        with self._lock:
            self._purge_expired_key(key)
            hash_value = self._hashes.get(key)
            if not hash_value:
                return 0
            removed = 0
            for field in fields:
                if field in hash_value:
                    hash_value.pop(field, None)
                    removed += 1
            if not hash_value:
                self._hashes.pop(key, None)
                self._expires_at.pop(key, None)
            return removed

    async def hlen(self, key: str) -> int:
        self._record("hlen")
        with self._lock:
            self._purge_expired_key(key)
            return len(self._hashes.get(key) or {})

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
