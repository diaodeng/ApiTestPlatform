"""工单相似工单查询结果缓存服务。

将相似工单查询的最终结果按 `工单ID + limit + 配置指纹` 缓存到 Redis，
避免同一张工单被反复打开详情时重复执行向量扫描与重排计算。

设计约束：
- 相似查询链路是同步服务（controller 用 run_in_threadpool 包裹），
  因此本服务使用 redis 的同步客户端独立建池；与 asyncio 客户端
  （app.state.redis）共用同一 Redis 实例，通过 key 前缀隔离。
- 缓存后端跟随 CACHE_BACKEND 配置：redis 时使用同步 Redis 连接池；
  memory 时降级为进程内 TTL 字典，保证单机开发环境可用。
- 缓存值只允许存 JSON 可序列化的相似结果 dict；读取失败一律视为未命中，
  不阻断真实查询链路。
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import redis as sync_redis

from config.env import RedisConfig
from utils.log_util import logger


class TicketSimilarResultCacheService:
    """
    相似工单查询结果缓存服务。

    缓存键包含 limit 与配置指纹：相似度配置（sys_config 的 ticket.similarity.config）
    变更或查询数量不同都会自然产生新键，旧键随 TTL 过期淘汰。
    """

    KEY_PREFIX = "ticket:similar-result"
    # 相似结果允许的过期窗口：工单更新时会主动失效，TTL 只是兜底
    TTL_SECONDS = 5 * 60
    # 进程内缓存最大条目数，超过后按写入时间淘汰最旧条目（仅 memory 后端使用）
    MAX_MEMORY_ENTRIES = 500

    _redis_pool: Any = None
    _redis_pool_lock = threading.Lock()
    # memory 后端使用的进程内存储：key -> (过期时间戳, JSON 字符串)
    _memory_store: dict[str, tuple[float, str]] = {}
    _memory_lock = threading.Lock()

    @classmethod
    def _get_redis(cls) -> Any:
        """
        懒加载同步 Redis 连接池，进程内复用。
        :return: 同步 Redis 客户端；连接失败时返回 None 并降级为直查
        """
        if cls._redis_pool is not None:
            return cls._redis_pool
        with cls._redis_pool_lock:
            if cls._redis_pool is not None:
                return cls._redis_pool
            try:
                cls._redis_pool = sync_redis.Redis(
                    host=RedisConfig.redis_host,
                    port=RedisConfig.redis_port,
                    username=RedisConfig.redis_username or None,
                    password=RedisConfig.redis_password or None,
                    db=RedisConfig.redis_database,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                    health_check_interval=30,
                )
                cls._redis_pool.ping()
                logger.info("相似结果缓存已连接 Redis")
            except Exception as exc:
                logger.warning(f"相似结果缓存连接 Redis 失败，降级为直查: {exc}")
                cls._redis_pool = None
            return cls._redis_pool

    @classmethod
    def build_key(cls, ticket_id: int, limit: int, config_fingerprint: str) -> str:
        """
        构建缓存键。
        :param ticket_id: 源工单ID
        :param limit: 查询数量
        :param config_fingerprint: 相似度配置指纹（取配置原始内容哈希）
        :return: 缓存键
        """
        return f"{cls.KEY_PREFIX}:{int(ticket_id)}:{int(limit)}:{config_fingerprint}"

    @classmethod
    def get(cls, key: str) -> dict[str, Any] | None:
        """
        读取缓存结果；任何异常都视为未命中，不抛出。
        :param key: 缓存键
        :return: 相似结果 dict 或 None
        """
        try:
            if RedisConfig.cache_backend == "memory":
                return cls._memory_get(key)
            client = cls._get_redis()
            if client is None:
                return None
            raw = client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning(f"相似结果缓存读取失败，视为未命中: key={key}, error={exc}")
            return None

    @classmethod
    def set(cls, key: str, result: dict[str, Any]) -> None:
        """
        写入缓存结果；任何异常都只记录日志，不影响主流程。
        :param key: 缓存键
        :param result: 相似查询结果 dict（必须 JSON 可序列化）
        """
        try:
            payload = json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            logger.warning(f"相似结果缓存序列化失败，跳过写入: key={key}, error={exc}")
            return
        try:
            if RedisConfig.cache_backend == "memory":
                cls._memory_set(key, payload)
                return
            client = cls._get_redis()
            if client is None:
                return
            client.set(key, payload, ex=cls.TTL_SECONDS)
        except Exception as exc:
            logger.warning(f"相似结果缓存写入失败: key={key}, error={exc}")

    @classmethod
    def invalidate_ticket(cls, ticket_id: int) -> int:
        """
        按工单失效该工单全部相似结果缓存（覆盖常见 limit 取值）。
        :param ticket_id: 工单ID
        :return: 删除的缓存条数
        """
        ticket_id = int(ticket_id)
        try:
            if RedisConfig.cache_backend == "memory":
                with cls._memory_lock:
                    keys = [key for key in cls._memory_store if key.startswith(f"{cls.KEY_PREFIX}:{ticket_id}:")]
                    for key in keys:
                        cls._memory_store.pop(key, None)
                    return len(keys)
            client = cls._get_redis()
            if client is None:
                return 0
            # limit 在 1~100 范围内逐个删除；实际常用值只有 5，扫描一次即可
            pattern = f"{cls.KEY_PREFIX}:{ticket_id}:*"
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted += client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.warning(f"相似结果缓存失效失败: ticket_id={ticket_id}, error={exc}")
            return 0

    @classmethod
    def _memory_get(cls, key: str) -> dict[str, Any] | None:
        """memory 后端读取，带过期与容量淘汰。"""
        with cls._memory_lock:
            item = cls._memory_store.get(key)
            if not item:
                return None
            expires_at, payload = item
            if expires_at < time.time():
                cls._memory_store.pop(key, None)
                return None
            data = json.loads(payload)
            return data if isinstance(data, dict) else None

    @classmethod
    def _memory_set(cls, key: str, payload: str) -> None:
        """memory 后端写入，超容量时淘汰最旧条目。"""
        with cls._memory_lock:
            if len(cls._memory_store) >= cls.MAX_MEMORY_ENTRIES and key not in cls._memory_store:
                oldest_key = min(cls._memory_store, key=lambda k: cls._memory_store[k][0])
                cls._memory_store.pop(oldest_key, None)
            cls._memory_store[key] = (time.time() + cls.TTL_SECONDS, payload)
