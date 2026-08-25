from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder

from config.env import RedisInitKeyConfig
from module_qtr.service.agent_service import AgentResponseEnum, HandleResponse, handle_response
from module_qtr.service.agent_service import agents as connected_agents
from module_qtr.service.agent_service import send_message as agent_send_message
from module_qtr.util.agent_dispatch_config import (
    AGENT_AI_ANALYSIS_ACTIVE_LEASE_BUFFER_SECONDS,
    AGENT_AI_ANALYSIS_ACTIVE_PREFIX,
    AGENT_AI_ANALYSIS_LOCK_PREFIX,
    AGENT_AI_ANALYSIS_LOCK_TTL_SECONDS,
    AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_CONFIG_KEY,
    AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_DEFAULT,
    AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS,
    AGENT_AI_ANALYSIS_QUEUE_PREFIX,
    AGENT_AI_ANALYSIS_REQUEST_PREFIX,
    AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
    AGENT_AI_ANALYSIS_RESULT_PREFIX,
    AGENT_AI_ANALYSIS_RESULT_TTL_SECONDS,
    AGENT_AI_ANALYSIS_STATE_PREFIX,
)
from utils.log_util import logger


class AgentDispatchService:
    """
    Agent 跨进程派发服务。

    负责 AI 分析任务的排队、并发配额和请求转发，保证 Celery/后台任务与 FastAPI WebSocket 网关之间的
    交互不再依赖进程内内存状态。
    """

    @classmethod
    def _queue_key(cls, agent_code: str) -> str:
        """生成指定 Agent 的排队键。"""
        return f"{AGENT_AI_ANALYSIS_QUEUE_PREFIX}:{agent_code}"

    @classmethod
    def _active_key(cls, agent_code: str) -> str:
        """生成指定 Agent 的运行中任务键。"""
        return f"{AGENT_AI_ANALYSIS_ACTIVE_PREFIX}:{agent_code}"

    @classmethod
    def _request_key(cls, request_id: str) -> str:
        """生成请求内容缓存键。"""
        return f"{AGENT_AI_ANALYSIS_REQUEST_PREFIX}:{request_id}"

    @classmethod
    def _state_key(cls, request_id: str) -> str:
        """生成请求状态缓存键。"""
        return f"{AGENT_AI_ANALYSIS_STATE_PREFIX}:{request_id}"

    @classmethod
    def _result_key(cls, request_id: str) -> str:
        """生成请求结果缓存键。"""
        return f"{AGENT_AI_ANALYSIS_RESULT_PREFIX}:{request_id}"

    @classmethod
    def _lock_key(cls, agent_code: str) -> str:
        """生成指定 Agent 的分发锁键。"""
        return f"{AGENT_AI_ANALYSIS_LOCK_PREFIX}:{agent_code}"

    @classmethod
    def _normalize_request_id(cls, request_id: str | None) -> str:
        """规范化请求ID。"""
        normalized = str(request_id or "").strip()
        return normalized or uuid.uuid4().hex

    @classmethod
    async def _resolve_max_concurrent_tasks(cls, redis) -> int:
        """
        从系统参数缓存中读取 Agent 的最大并发任务数。
        :param redis: Redis 连接
        :return: 最大并发数，最小为 1
        """
        config_key = f"{RedisInitKeyConfig.SYS_CONFIG.get('key')}:{AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_CONFIG_KEY}"
        raw_value = await redis.get(config_key)
        try:
            resolved = int(str(raw_value or "").strip() or AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_DEFAULT)
        except Exception:
            resolved = AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_DEFAULT
        return max(resolved, 1)

    @classmethod
    async def _acquire_lock(cls, redis, lock_key: str) -> str | None:
        """
        尝试获取短时分发锁。
        :param redis: Redis 连接
        :param lock_key: 锁键名
        :return: 锁 token，获取失败时返回 None
        """
        lock_token = uuid.uuid4().hex
        try:
            locked = await redis.set(lock_key, lock_token, nx=True, ex=AGENT_AI_ANALYSIS_LOCK_TTL_SECONDS)
        except TypeError:
            locked = await redis.setnx(lock_key, lock_token)
            if locked:
                await redis.expire(lock_key, AGENT_AI_ANALYSIS_LOCK_TTL_SECONDS)
        return lock_token if locked else None

    @classmethod
    async def _release_lock(cls, redis, lock_key: str, lock_token: str | None) -> None:
        """
        释放分发锁，避免错误删除别的协程刚获得的锁。
        :param redis: Redis 连接
        :param lock_key: 锁键名
        :param lock_token: 当前持有的 token
        :return: 无
        """
        if not lock_token:
            return
        try:
            current_token = await redis.get(lock_key)
            if current_token == lock_token:
                await redis.delete(lock_key)
        except Exception:
            pass

    @classmethod
    async def _cleanup_expired_active_requests(cls, redis, agent_code: str) -> None:
        """
        清理已过期的运行中租约，避免异常断开后并发槽位被永久占用。
        :param redis: Redis 连接
        :param agent_code: Agent 编码
        :return: 无
        """
        active_key = cls._active_key(agent_code)
        now_ts = int(time.time())
        active_items = await redis.hgetall(active_key)
        expired_request_ids = [
            request_id for request_id, expires_at in active_items.items() if int(str(expires_at or "0")) <= now_ts
        ]
        if expired_request_ids:
            await redis.hdel(active_key, *expired_request_ids)

    @classmethod
    async def _serialize_state(
        cls,
        *,
        request_id: str,
        agent_code: str,
        status: str,
        timeout_seconds: int | float | None,
        message: dict[str, Any],
    ) -> str:
        """序列化请求状态。"""
        payload = {
            "requestId": request_id,
            "agentCode": agent_code,
            "status": status,
            "timeoutSeconds": timeout_seconds,
            "requestType": message.get("requestType"),
            "command": message.get("command"),
            "updatedAt": int(time.time()),
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    async def _cache_request(
        cls,
        redis,
        *,
        request_id: str,
        agent_code: str,
        message: dict[str, Any],
        timeout_seconds: int | float | None,
    ) -> None:
        """
        将待分发请求写入 Redis，供排队和重试使用。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :param agent_code: Agent 编码
        :param message: 请求消息体
        :param timeout_seconds: 请求超时时间
        :return: 无
        """
        request_key = cls._request_key(request_id)
        state_key = cls._state_key(request_id)
        request_payload = {
            "requestId": request_id,
            "agentCode": agent_code,
            "message": message,
            "timeoutSeconds": timeout_seconds,
            "createdAt": int(time.time()),
        }
        await redis.set(
            request_key,
            json.dumps(jsonable_encoder(request_payload), ensure_ascii=False),
            ex=AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
        )
        current_state = await redis.get(state_key)
        if not current_state:
            await redis.set(
                state_key,
                await cls._serialize_state(
                    request_id=request_id,
                    agent_code=agent_code,
                    status="queued",
                    timeout_seconds=timeout_seconds,
                    message=message,
                ),
                ex=AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
            )
            await redis.rpush(cls._queue_key(agent_code), request_id)

    @classmethod
    async def _load_cached_result(cls, redis, request_id: str) -> HandleResponse | None:
        """
        读取已完成请求的缓存结果。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :return: 已缓存的响应对象，未命中则返回 None
        """
        cached_result = await redis.get(cls._result_key(request_id))
        if not cached_result:
            return None
        try:
            return HandleResponse.model_validate_json(cached_result)
        except Exception:
            logger.warning(f"解析缓存的 Agent 响应失败，request_id={request_id}")
            return None

    @classmethod
    async def _store_result(cls, redis, request_id: str, response: HandleResponse) -> None:
        """
        持久化 Agent 响应缓存，便于重复提交时快速返回。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :param response: 响应对象
        :return: 无
        """
        try:
            serialized = json.dumps(jsonable_encoder(response), ensure_ascii=False)
        except Exception as exc:
            logger.warning(f"序列化 Agent 响应失败，request_id={request_id}, error={exc}")
            serialized = json.dumps(
                {
                    "statusCode": response.status_code,
                    "message": response.message,
                    "response": None,
                },
                ensure_ascii=False,
            )
        await redis.set(cls._result_key(request_id), serialized, ex=AGENT_AI_ANALYSIS_RESULT_TTL_SECONDS)

    @classmethod
    async def _mark_state(cls, redis, request_id: str, agent_code: str, status: str, message: dict[str, Any]) -> None:
        """
        更新请求状态缓存。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :param agent_code: Agent 编码
        :param status: 状态值
        :param message: 请求消息体
        :return: 无
        """
        await redis.set(
            cls._state_key(request_id),
            await cls._serialize_state(
                request_id=request_id,
                agent_code=agent_code,
                status=status,
                timeout_seconds=message.get("timeoutSeconds"),
                message=message,
            ),
            ex=AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
        )

    @classmethod
    async def _try_admit_request(
        cls,
        redis,
        *,
        agent_code: str,
        request_id: str,
        message: dict[str, Any],
        max_concurrent_tasks: int,
        lease_seconds: int,
    ) -> bool:
        """
        尝试为当前请求抢占一个运行槽位。
        :param redis: Redis 连接
        :param agent_code: Agent 编码
        :param request_id: 请求ID
        :param message: 请求消息体
        :param max_concurrent_tasks: 最大并发任务数
        :param lease_seconds: 租约时长
        :return: 是否成功抢占
        """
        lock_key = cls._lock_key(agent_code)
        lock_token = await cls._acquire_lock(redis, lock_key)
        if not lock_token:
            return False
        try:
            await cls._cleanup_expired_active_requests(redis, agent_code)
            if request_id == await redis.lindex(cls._queue_key(agent_code), 0):
                active_count = await redis.hlen(cls._active_key(agent_code))
                if active_count >= max_concurrent_tasks:
                    return False
                await redis.hset(
                    cls._active_key(agent_code),
                    request_id,
                    str(int(time.time()) + lease_seconds),
                )
                await redis.lpop(cls._queue_key(agent_code))
                await cls._mark_state(redis, request_id, agent_code, "running", message)
                return True
            return False
        finally:
            await cls._release_lock(redis, lock_key, lock_token)

    @classmethod
    async def send_ai_analysis_message(
        cls,
        redis,
        agent_code: str,
        message: dict[str, Any],
        request_id: str | None = None,
        timeout_seconds: int | float | None = None,
    ) -> HandleResponse:
        """
        按 Agent 并发上限排队并转发 AI 分析请求。
        :param redis: Redis 连接
        :param agent_code: Agent 编码
        :param message: 要转发给 Agent 的请求消息
        :param request_id: 请求ID，默认自动生成
        :param timeout_seconds: 等待队列和 Agent 响应的总超时时间
        :return: Agent 响应对象
        """
        request_id = cls._normalize_request_id(request_id)
        request_message = dict(message or {})
        request_message["request_id"] = request_id
        request_message["timeoutSeconds"] = timeout_seconds

        cached_response = await cls._load_cached_result(redis, request_id)
        if cached_response:
            return cached_response

        request_timeout = max(float(timeout_seconds or 120), 1.0)
        lease_seconds = max(int(request_timeout) + AGENT_AI_ANALYSIS_ACTIVE_LEASE_BUFFER_SECONDS, 600)
        deadline = time.monotonic() + request_timeout
        await cls._cache_request(
            redis,
            request_id=request_id,
            agent_code=agent_code,
            message=request_message,
            timeout_seconds=timeout_seconds,
        )
        logger.info(
            f"AI 分析请求进入 Agent 队列 | agent_code={agent_code}, request_id={request_id}, "
            f"timeout_seconds={timeout_seconds}, request_type={request_message.get('requestType')}"
        )

        while True:
            if time.monotonic() >= deadline:
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await redis.hdel(cls._active_key(agent_code), request_id)
                await cls._mark_state(redis, request_id, agent_code, "timeout", request_message)
                logger.warning(
                    f"AI 分析请求排队超时 | agent_code={agent_code}, request_id={request_id}, "
                    f"timeout_seconds={timeout_seconds}"
                )
                return handle_response(
                    (
                        AgentResponseEnum.OPERATION_TIMEOUT.value,
                        None,
                        f"Agent[{agent_code}] AI 分析请求排队等待超时，request_id={request_id}",
                    )
                )

            cached_response = await cls._load_cached_result(redis, request_id)
            if cached_response:
                return cached_response

            if agent_code not in connected_agents:
                await asyncio.sleep(AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS)
                continue

            admitted = await cls._try_admit_request(
                redis,
                agent_code=agent_code,
                request_id=request_id,
                message=request_message,
                max_concurrent_tasks=await cls._resolve_max_concurrent_tasks(redis),
                lease_seconds=lease_seconds,
            )
            if not admitted:
                queue_head = await redis.lindex(cls._queue_key(agent_code), 0)
                if queue_head and not await redis.exists(cls._request_key(queue_head)):
                    await redis.lpop(cls._queue_key(agent_code))
                logger.info(
                    f"AI 分析请求等待 Agent 槽位 | agent_code={agent_code}, request_id={request_id}, "
                    f"queue_head={queue_head or '-'}, active_count={await redis.hlen(cls._active_key(agent_code))}, "
                    f"max_concurrent={await cls._resolve_max_concurrent_tasks(redis)}"
                )
                await asyncio.sleep(AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS)
                continue
            logger.info(
                f"AI 分析请求获得 Agent 槽位 | agent_code={agent_code}, request_id={request_id}, "
                f"lease_seconds={lease_seconds}"
            )

            try:
                remaining_timeout_seconds = max(deadline - time.monotonic(), 1.0)
                request_message["timeoutSeconds"] = remaining_timeout_seconds
                response = await agent_send_message(
                    agent_code,
                    request_message,
                    request_id=request_id,
                    timeout_seconds=remaining_timeout_seconds,
                )
                if response.status_code == AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value:
                    logger.info(
                        f"Agent[{agent_code}] 连接已断开，AI 分析请求重新入队，request_id={request_id}"
                    )
                    await redis.hdel(cls._active_key(agent_code), request_id)
                    await redis.lpush(cls._queue_key(agent_code), request_id)
                    await cls._mark_state(redis, request_id, agent_code, "queued", request_message)
                    await asyncio.sleep(AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS)
                    continue
                await cls._store_result(redis, request_id, response)
                await cls._mark_state(redis, request_id, agent_code, "completed", request_message)
                logger.info(
                    f"AI 分析请求完成 | agent_code={agent_code}, request_id={request_id}, "
                    f"status_code={response.status_code}"
                )
                return response
            except asyncio.CancelledError as exc:
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await redis.hdel(cls._active_key(agent_code), request_id)
                await cls._mark_state(redis, request_id, agent_code, "cancelled", request_message)
                logger.warning(
                    f"AI 分析请求被取消 | agent_code={agent_code}, request_id={request_id}, error={exc}"
                )
                return handle_response((AgentResponseEnum.TASK_CANCELLED.value, None, str(exc.args)))
            except Exception as exc:
                await redis.hdel(cls._active_key(agent_code), request_id)
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await cls._mark_state(redis, request_id, agent_code, "failed", request_message)
                logger.exception(f"Agent[{agent_code}] AI 分析请求执行异常，request_id={request_id}, error={exc}")
                return handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, None, str(exc)))
            finally:
                await redis.hdel(cls._active_key(agent_code), request_id)
