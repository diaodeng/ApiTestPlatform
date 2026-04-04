from __future__ import annotations

from typing import Any

from redis import asyncio as aioredis
from redis.exceptions import AuthenticationError, RedisError, TimeoutError

from config.cache_backend import MemoryRedis
from config.database import SessionLocal
from config.env import RedisConfig
from module_admin.service.config_service import ConfigService
from module_admin.service.dict_service import DictDataService
from utils.log_util import logger


CACHE_BACKEND = (RedisConfig.cache_backend or "redis").strip().lower()


class RedisUtil:
    """
    缓存相关方法。保留原名称，底层可切换 Redis / Memory。
    """

    @classmethod
    async def create_redis_pool(cls) -> Any:
        """
        应用启动时初始化缓存连接
        :return: Redis连接对象或内存缓存对象
        """
        if CACHE_BACKEND == "memory":
            logger.info("缓存后端使用 memory")
            cache = MemoryRedis()
            await cache.ping()
            return cache

        logger.info("开始连接redis...")
        redis = await aioredis.from_url(
            url=f"redis://{RedisConfig.redis_host}",
            port=RedisConfig.redis_port,
            username=RedisConfig.redis_username,
            password=RedisConfig.redis_password,
            db=RedisConfig.redis_database,
            encoding="utf-8",
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
        )
        try:
            connection = await redis.ping()
            if connection:
                logger.info("redis连接成功")
            else:
                logger.error("redis连接失败")
        except AuthenticationError as exc:
            logger.error(f"redis用户名或密码错误，详细错误信息：{exc}")
        except TimeoutError as exc:
            logger.error(f"redis连接超时，详细错误信息：{exc}")
        except RedisError as exc:
            logger.error(f"redis连接错误，详细错误信息：{exc}")
        return redis

    @classmethod
    async def close_redis_pool(cls, app):
        """
        应用关闭时关闭缓存连接
        :param app: fastapi对象
        :return:
        """
        if getattr(app.state, "redis", None) is not None:
            await app.state.redis.close()
        logger.info("关闭缓存连接成功")

    @classmethod
    async def init_sys_dict(cls, redis):
        """
        应用启动时缓存字典表
        :param redis: 缓存对象
        :return:
        """
        session = SessionLocal()
        try:
            await DictDataService.init_cache_sys_dict_services(session, redis)
        finally:
            session.close()

    @classmethod
    async def init_sys_config(cls, redis):
        """
        应用启动时缓存参数配置表
        :param redis: 缓存对象
        :return:
        """
        session = SessionLocal()
        try:
            await ConfigService.init_cache_sys_config_services(session, redis)
        finally:
            session.close()
