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
    AGENT_AI_ANALYSIS_DISCONNECT_REQUEUE_LIMIT,
    AGENT_AI_ANALYSIS_LOCK_PREFIX,
    AGENT_AI_ANALYSIS_LOCK_TTL_SECONDS,
    AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_CONFIG_KEY,
    AGENT_AI_ANALYSIS_MAX_CONCURRENT_TASKS_DEFAULT,
    AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS,
    AGENT_AI_ANALYSIS_QUEUE_PREFIX,
    AGENT_AI_ANALYSIS_QUEUED_LEASE_RENEW_INTERVAL_SECONDS,
    AGENT_AI_ANALYSIS_QUEUED_LEASE_SECONDS,
    AGENT_AI_ANALYSIS_REQUEST_PREFIX,
    AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
    AGENT_AI_ANALYSIS_RESULT_PREFIX,
    AGENT_AI_ANALYSIS_RESULT_TTL_SECONDS,
    AGENT_AI_ANALYSIS_STATE_PREFIX,
    AGENT_AI_ANALYSIS_WAIT_LOG_INTERVAL_SECONDS,
)
from utils.log_util import logger


class AgentDispatchService:
    """
    Agent 跨进程派发服务。

    负责 AI 分析任务的排队、并发配额和请求转发，保证 Celery/后台任务与 FastAPI WebSocket 网关之间的
    交互不再依赖进程内内存状态。
    """

    TERMINAL_REQUEST_STATUSES = frozenset({"completed", "failed", "timeout", "cancelled"})

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
    def _build_state_message(cls, message: dict[str, Any], timeout_seconds: int | float | None) -> dict[str, Any]:
        """
        提取状态缓存所需的轻量请求元数据，避免排队协程长期持有完整大请求。
        :param message: 原始请求消息
        :param timeout_seconds: 总超时时间
        :return: 轻量消息字典
        """
        return {
            "requestType": message.get("requestType"),
            "command": message.get("command"),
            "timeoutSeconds": timeout_seconds,
        }

    @classmethod
    def _build_queue_lease_until(cls) -> int:
        """
        生成排队请求的心跳租约截止时间戳。
        :return: Unix 时间戳（秒）
        """
        return int(time.time()) + AGENT_AI_ANALYSIS_QUEUED_LEASE_SECONDS

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
        :param redis: 连接
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
    async def cleanup_orphan_active_leases(cls, redis) -> int:
        """
        服务重启后清理所有 Agent 的遗留运行租约（孤儿租约）。

        背景：进程被 OOM Kill 时，等待 Agent 响应的协程随进程死亡，但
        active 租约（最长 3900 秒）仍留在 Redis 中占满并发槽位，导致重启后
        的重试请求排队等待直到旧租约自然过期（实测阻塞 24 分钟）。
        服务启动阶段调用本方法：此刻不可能存在真正在运行的请求（Agent
        请求只由本进程发出且进程刚启动），因此直接清空全部租约是安全的；
        Agent 若在重启期间完成执行，其结果由迟到结果缓存机制恢复，不依赖
        该租约。

        :param redis: Redis 连接
        :return: 清理的租约数量
        """
        removed = 0
        pattern = f"{AGENT_AI_ANALYSIS_ACTIVE_PREFIX}:*"
        try:
            # 用 SCAN 游标循环而非 scan_iter：MemoryRedis（测试后端）只实现 scan。
            cursor: int | str = 0
            agent_keys: list[str] = []
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
                agent_keys.extend(str(key) for key in keys)
                if int(cursor) == 0:
                    break
            for agent_key in agent_keys:
                active_items = await redis.hgetall(agent_key)
                if not active_items:
                    continue
                agent_code = agent_key.rsplit(":", 1)[-1]
                # 按请求粒度删除并记录状态，保证观测性；重启场景下全部视为孤儿。
                request_ids = list(active_items.keys())
                await redis.hdel(agent_key, *request_ids)
                removed += len(request_ids)
                for request_id in request_ids:
                    await cls._mark_state(
                        redis,
                        request_id=request_id,
                        agent_code=agent_code,
                        status="failed",
                        message={
                            "extra": {
                                "reason": "orphan-lease-cleanup-on-restart",
                            },
                        },
                    )
                logger.warning(
                    f"服务重启清理遗留 Agent 运行租约 | agent={agent_code}, "
                    f"count={len(request_ids)}, request_ids={[str(r) for r in request_ids]}"
                )
        except Exception as exc:
            logger.warning(f"清理遗留 Agent 运行租约失败（不影响启动）: error={exc}")
        return removed

    @classmethod
    async def _load_json_cache(cls, redis, cache_key: str) -> dict[str, Any] | None:
        """
        读取并解析 JSON 格式的 Redis 缓存。
        :param redis: Redis 连接
        :param cache_key: 缓存键
        :return: 解析后的字典，异常或不存在时返回 None
        """
        raw_payload = await redis.get(cache_key)
        if not raw_payload:
            return None
        try:
            payload = json.loads(raw_payload)
        except Exception as exc:
            logger.warning(f"解析 Agent 分发缓存失败 | cache_key={cache_key}, error={exc}")
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _to_int(cls, value: Any) -> int | None:
        """
        将输入安全转换为整数。
        :param value: 任意输入值
        :return: 转换后的整数，失败时返回 None
        """
        try:
            return int(str(value or "").strip())
        except Exception:
            return None

    @classmethod
    def _to_float(cls, value: Any) -> float | None:
        """
        将输入安全转换为浮点数。
        :param value: 任意输入值
        :return: 转换后的浮点数，失败时返回 None
        """
        try:
            return float(str(value or "").strip())
        except Exception:
            return None

    @classmethod
    async def _resolve_stale_queue_head_reason(cls, redis, agent_code: str, request_id: str) -> str | None:
        """
        判断队列头请求是否已经失效。
        :param redis: Redis 连接
        :param agent_code: Agent 编码
        :param request_id: 队列头请求ID
        :return: 失效原因；仍然有效时返回 None
        """
        if not request_id:
            return "empty-request-id"

        request_key = cls._request_key(request_id)
        if not await redis.exists(request_key):
            return "request-cache-missing"

        now_ts = time.time()
        state_payload = await cls._load_json_cache(redis, cls._state_key(request_id))
        status = str((state_payload or {}).get("status") or "").strip()
        if status in cls.TERMINAL_REQUEST_STATUSES:
            return f"terminal-status:{status}"

        active_items = await redis.hgetall(cls._active_key(agent_code))
        active_expires_at = (active_items or {}).get(request_id)
        if active_expires_at is not None:
            expires_at = cls._to_int(active_expires_at)
            if expires_at is None:
                return "active-lease-invalid"
            if expires_at <= int(now_ts):
                return "active-lease-expired"
            return None

        queued_lease_until = cls._to_int((state_payload or {}).get("queueLeaseUntil"))
        state_updated_at = cls._to_int((state_payload or {}).get("updatedAt"))
        if status == "queued":
            if queued_lease_until is not None and queued_lease_until <= int(now_ts):
                return "queued-lease-expired"
            if (
                queued_lease_until is None
                and state_updated_at is not None
                and state_updated_at + AGENT_AI_ANALYSIS_QUEUED_LEASE_SECONDS <= now_ts
            ):
                return "queued-heartbeat-expired"

        request_payload = await cls._load_json_cache(redis, request_key)
        created_at = cls._to_int((request_payload or {}).get("createdAt")) or state_updated_at
        timeout_seconds = cls._to_float((request_payload or {}).get("timeoutSeconds"))
        if timeout_seconds is None:
            timeout_seconds = cls._to_float((state_payload or {}).get("timeoutSeconds"))
        if timeout_seconds is None:
            timeout_seconds = 120.0
        if created_at is None:
            return None
        if created_at + max(timeout_seconds, 1.0) <= now_ts:
            return "request-timeout-elapsed-without-active-lease"
        return None

    @classmethod
    async def _cleanup_stale_queue_head(cls, redis, agent_code: str) -> str | None:
        """
        清理队列头部已经失效的请求，避免陈旧任务永久阻塞后续分析。
        :param redis: Redis 连接
        :param agent_code: Agent 编码
        :return: 清理后的有效队列头请求ID；队列为空时返回 None
        """
        queue_key = cls._queue_key(agent_code)
        while True:
            queue_head = await redis.lindex(queue_key, 0)
            if not queue_head:
                return None
            stale_reason = await cls._resolve_stale_queue_head_reason(redis, agent_code, queue_head)
            if not stale_reason:
                return queue_head
            await redis.lpop(queue_key)
            await redis.hdel(cls._active_key(agent_code), queue_head)
            logger.warning(
                f"AI 分析请求队列头已自动清理 | agent_code={agent_code}, "
                f"stale_request_id={queue_head}, reason={stale_reason}"
            )

    @classmethod
    async def _serialize_state(
        cls,
        *,
        request_id: str,
        agent_code: str,
        status: str,
        timeout_seconds: int | float | None,
        message: dict[str, Any],
        queued_lease_until: int | None = None,
    ) -> str:
        """
        序列化请求状态。
        :param request_id: 请求ID
        :param agent_code: Agent 编码
        :param status: 状态值
        :param timeout_seconds: 总超时时间
        :param message: 轻量消息体
        :param queued_lease_until: 排队续租截止时间戳；非排队状态传 None
        :return: JSON 字符串
        """
        payload = {
            "requestId": request_id,
            "agentCode": agent_code,
            "status": status,
            "timeoutSeconds": timeout_seconds,
            "requestType": message.get("requestType"),
            "command": message.get("command"),
            "updatedAt": int(time.time()),
        }
        if queued_lease_until is not None:
            payload["queueLeaseUntil"] = queued_lease_until
        # 扩展说明字段：message 中的 reason 等诊断信息透传到状态缓存。
        extra = message.get("extra")
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in payload:
                    payload[key] = value
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
        :param message: 完整请求消息体
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
            await cls._mark_queued_state(
                redis,
                request_id=request_id,
                agent_code=agent_code,
                state_message=cls._build_state_message(message, timeout_seconds),
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
            return HandleResponse.validate_transport_payload(cached_result)
        except Exception:
            logger.warning(f"解析缓存的 Agent 响应失败，request_id={request_id}")
            return None

    @classmethod
    async def _load_cached_request_message(cls, redis, request_id: str) -> dict[str, Any] | None:
        """
        读取缓存中的完整请求消息体，仅在真正转发给 Agent 时恢复，减少排队阶段内存占用。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :return: 完整请求消息字典，缺失时返回 None
        """
        request_payload = await cls._load_json_cache(redis, cls._request_key(request_id))
        message = (request_payload or {}).get("message")
        return dict(message) if isinstance(message, dict) else None

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
    async def _mark_state(
        cls,
        redis,
        request_id: str,
        agent_code: str,
        status: str,
        message: dict[str, Any],
        queued_lease_until: int | None = None,
    ) -> None:
        """
        更新请求状态缓存。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :param agent_code: Agent 编码
        :param status: 状态值
        :param message: 轻量请求消息体
        :param queued_lease_until: 排队续租截止时间戳；非排队状态传 None
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
                queued_lease_until=queued_lease_until,
            ),
            ex=AGENT_AI_ANALYSIS_REQUEST_TTL_SECONDS,
        )

    @classmethod
    async def _mark_queued_state(
        cls,
        redis,
        *,
        request_id: str,
        agent_code: str,
        state_message: dict[str, Any],
    ) -> None:
        """
        将请求标记为排队中，并续租排队心跳。
        :param redis: Redis 连接
        :param request_id: 请求ID
        :param agent_code: Agent 编码
        :param state_message: 轻量请求消息体
        :return: 无
        """
        await cls._mark_state(
            redis,
            request_id,
            agent_code,
            "queued",
            state_message,
            queued_lease_until=cls._build_queue_lease_until(),
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
            queue_head = await cls._cleanup_stale_queue_head(redis, agent_code)
            if request_id == queue_head:
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
        state_message = cls._build_state_message(request_message, timeout_seconds)

        cached_response = await cls._load_cached_result(redis, request_id)
        if cached_response:
            return cached_response

        # 提交时 Agent 已离线：立即失败并返回明确原因，不再进入队列空转到总超时，
        # 避免"AI 分析中"假象（INC00001967826 类问题：排队等待一小时才超时）。
        if agent_code not in connected_agents:
            logger.warning(
                f"AI 分析请求提交失败：Agent 离线 | agent_code={agent_code}, request_id={request_id}"
            )
            return handle_response(
                (
                    AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value,
                    None,
                    f"Agent[{agent_code}] 当前离线，AI 分析任务未下发，请确认 Agent 已连接后重试",
                )
            )

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
            f"timeout_seconds={timeout_seconds}, request_type={state_message.get('requestType')}"
        )
        # 排队阶段只保留轻量状态元数据；完整请求消息在真正拿到槽位时再从 Redis 恢复，
        # 避免多个等待协程在内存中同时持有大体积 prompt / context / schema。
        request_message = None
        next_queue_renew_at = 0.0
        next_wait_log_at = 0.0
        disconnect_requeue_count = 0

        while True:
            now_mono = time.monotonic()
            if now_mono >= deadline:
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await redis.hdel(cls._active_key(agent_code), request_id)
                await cls._mark_state(redis, request_id, agent_code, "timeout", state_message)
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

            if now_mono >= next_queue_renew_at:
                await cls._mark_queued_state(
                    redis,
                    request_id=request_id,
                    agent_code=agent_code,
                    state_message=state_message,
                )
                next_queue_renew_at = now_mono + AGENT_AI_ANALYSIS_QUEUED_LEASE_RENEW_INTERVAL_SECONDS

            if agent_code not in connected_agents:
                # 排队期间 Agent 掉线：立即失败，不再空转等待到总超时。
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await redis.hdel(cls._active_key(agent_code), request_id)
                await cls._mark_state(redis, request_id, agent_code, "failed", state_message)
                logger.warning(
                    f"AI 分析请求排队期间 Agent 离线，立即失败 | "
                    f"agent_code={agent_code}, request_id={request_id}"
                )
                return handle_response(
                    (
                        AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value,
                        None,
                        f"Agent[{agent_code}] 排队期间连接断开，AI 分析任务未执行，请稍后重试",
                    )
                )

            max_concurrent_tasks = await cls._resolve_max_concurrent_tasks(redis)
            admitted = await cls._try_admit_request(
                redis,
                agent_code=agent_code,
                request_id=request_id,
                message=state_message,
                max_concurrent_tasks=max_concurrent_tasks,
                lease_seconds=lease_seconds,
            )
            if not admitted:
                if now_mono >= next_wait_log_at:
                    queue_head = await redis.lindex(cls._queue_key(agent_code), 0)
                    active_count = await redis.hlen(cls._active_key(agent_code))
                    logger.info(
                        f"AI 分析请求等待 Agent 槽位 | agent_code={agent_code}, request_id={request_id}, "
                        f"queue_head={queue_head or '-'}, active_count={active_count}, "
                        f"max_concurrent={max_concurrent_tasks}"
                    )
                    next_wait_log_at = now_mono + AGENT_AI_ANALYSIS_WAIT_LOG_INTERVAL_SECONDS
                await asyncio.sleep(AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS)
                continue
            logger.info(
                f"AI 分析请求获得 Agent 槽位 | agent_code={agent_code}, request_id={request_id}, "
                f"lease_seconds={lease_seconds}"
            )

            try:
                request_message = await cls._load_cached_request_message(redis, request_id)
                if not request_message:
                    await redis.hdel(cls._active_key(agent_code), request_id)
                    await cls._mark_state(redis, request_id, agent_code, "failed", state_message)
                    logger.warning(
                        f"AI 分析请求消息缓存缺失，无法转发到 Agent | "
                        f"agent_code={agent_code}, request_id={request_id}"
                    )
                    return handle_response(
                        (
                            AgentResponseEnum.UNKNOWN_EXCEPTION.value,
                            None,
                            f"Agent[{agent_code}] AI 分析请求消息缓存不存在，request_id={request_id}",
                        )
                    )
                remaining_timeout_seconds = max(deadline - time.monotonic(), 1.0)
                request_message["timeoutSeconds"] = remaining_timeout_seconds
                response = await agent_send_message(
                    agent_code,
                    request_message,
                    request_id=request_id,
                    timeout_seconds=remaining_timeout_seconds,
                )
                if response.status_code == AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value:
                    disconnect_requeue_count += 1
                    if disconnect_requeue_count >= AGENT_AI_ANALYSIS_DISCONNECT_REQUEUE_LIMIT:
                        # 连续多次转发失败说明连接已不可用（如注册表中残留僵尸连接），
                        # 直接失败并给出明确原因，不再"入队-失败-再入队"空转到总超时。
                        await redis.hdel(cls._active_key(agent_code), request_id)
                        await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                        await cls._mark_state(redis, request_id, agent_code, "failed", state_message)
                        logger.warning(
                            f"Agent[{agent_code}] 连续 {disconnect_requeue_count} 次转发失败，AI 分析请求判定失败 | "
                            f"request_id={request_id}"
                        )
                        return handle_response(
                            (
                                AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value,
                                None,
                                f"Agent[{agent_code}] 连接不可用（连续 {disconnect_requeue_count} 次转发失败），"
                                f"AI 分析任务未执行，请稍后重试",
                            )
                        )
                    logger.info(
                        f"Agent[{agent_code}] 连接已断开，AI 分析请求重新入队 | "
                        f"request_id={request_id}, requeue_count={disconnect_requeue_count}"
                    )
                    await redis.hdel(cls._active_key(agent_code), request_id)
                    await redis.lpush(cls._queue_key(agent_code), request_id)
                    await cls._mark_queued_state(
                        redis,
                        request_id=request_id,
                        agent_code=agent_code,
                        state_message=state_message,
                    )
                    next_queue_renew_at = 0.0
                    next_wait_log_at = 0.0
                    await asyncio.sleep(AGENT_AI_ANALYSIS_POLL_INTERVAL_SECONDS)
                    continue
                disconnect_requeue_count = 0
                await cls._store_result(redis, request_id, response)
                await cls._mark_state(redis, request_id, agent_code, "completed", state_message)
                logger.info(
                    f"AI 分析请求完成 | agent_code={agent_code}, request_id={request_id}, "
                    f"status_code={response.status_code}"
                )
                return response
            except asyncio.CancelledError as exc:
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await redis.hdel(cls._active_key(agent_code), request_id)
                await cls._mark_state(redis, request_id, agent_code, "cancelled", state_message)
                logger.warning(
                    f"AI 分析请求因 Agent 连接断开被取消 | agent_code={agent_code}, request_id={request_id}, "
                    f"error={exc}"
                )
                # 专用错误码标识"连接中途断开"：区别于用户主动取消，工单侧据此进入
                # pending_recovery 状态等待 Agent 重连补交结果，而不是直接判定失败。
                return handle_response(
                    (
                        AgentResponseEnum.AGENT_CONNECTION_LOST.value,
                        None,
                        f"Agent[{agent_code}] 连接中断，任务执行被取消，等待 Agent 补交结果恢复",
                    )
                )
            except Exception as exc:
                await redis.hdel(cls._active_key(agent_code), request_id)
                await redis.lrem(cls._queue_key(agent_code), 0, request_id)
                await cls._mark_state(redis, request_id, agent_code, "failed", state_message)
                logger.exception(f"Agent[{agent_code}] AI 分析请求执行异常，request_id={request_id}, error={exc}")
                return handle_response((AgentResponseEnum.UNKNOWN_EXCEPTION.value, None, str(exc)))
            finally:
                await redis.hdel(cls._active_key(agent_code), request_id)
