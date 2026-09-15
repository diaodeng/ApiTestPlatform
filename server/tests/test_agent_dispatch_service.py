import asyncio
import json
import time

from config.cache_backend import MemoryRedis
from module_qtr.service import agent_dispatch_service as dispatch_module
from module_qtr.service.agent_dispatch_service import AgentDispatchService
from module_qtr.service.agent_service import AgentResponseEnum, AgentResponseWebUI, HandleResponse


def test_ai_analysis_dispatch_queues_over_agent_concurrency_limit():
    """
    单个 Agent 的并发上限为 1 时，后续 AI 分析请求应进入队列等待，直到前一个请求释放槽位。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        dispatch_module.connected_agents = {"agent-1": object()}
        started_requests: list[str | None] = []
        first_request_can_finish = asyncio.Event()

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, message, timeout_seconds
            started_requests.append(request_id)
            if len(started_requests) == 1:
                await first_request_can_finish.wait()
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "并发队列测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            first_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-test-1",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.2)
            assert started_requests == ["dispatch-test-1"]

            second_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-test-2",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.2)
            assert started_requests == ["dispatch-test-1"]

            first_request_can_finish.set()
            first_response = await first_task
            second_response = await second_task

            assert first_response.status_code == 200
            assert second_response.status_code == 200
            assert started_requests == ["dispatch-test-1", "dispatch-test-2"]
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())


def test_ai_analysis_dispatch_uses_remaining_timeout_after_queue_wait():
    """
    排队等待后，转发给 Agent 的超时应按剩余时间计算，避免总超时被拉长。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        dispatch_module.connected_agents = {"agent-1": object()}
        first_request_can_finish = asyncio.Event()
        received_timeouts: list[float | None] = []

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, message, request_id
            received_timeouts.append(timeout_seconds)
            if len(received_timeouts) == 1:
                await first_request_can_finish.wait()
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "剩余超时测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            first_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-timeout-1",
                    timeout_seconds=5,
                )
            )
            await asyncio.sleep(1.0)

            second_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-timeout-2",
                    timeout_seconds=5,
                )
            )
            await asyncio.sleep(1.0)
            first_request_can_finish.set()

            first_response = await first_task
            second_response = await second_task

            assert first_response.status_code == 200
            assert second_response.status_code == 200
            assert len(received_timeouts) == 2
            assert received_timeouts[0] is not None
            assert received_timeouts[1] is not None
            assert received_timeouts[1] < 5
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())

def test_ai_analysis_dispatch_cleans_stale_queue_head_before_admitting_new_request():
    """
    队列头请求已经超时且没有运行中租约时，应自动清理，避免后续 AI 分析永久卡在排队阶段。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        stale_request_id = "dispatch-stale-head"
        stale_message = {"requestType": 6, "command": "run_ticket_ai_analysis"}
        stale_request_payload = {
            "requestId": stale_request_id,
            "agentCode": "agent-1",
            "message": stale_message,
            "timeoutSeconds": 30,
            "createdAt": int(time.time()) - 120,
        }
        stale_state_payload = {
            "requestId": stale_request_id,
            "agentCode": "agent-1",
            "status": "queued",
            "timeoutSeconds": 30,
            "requestType": 6,
            "command": "run_ticket_ai_analysis",
            "updatedAt": int(time.time()) - 120,
        }
        await redis.set(
            AgentDispatchService._request_key(stale_request_id),
            json.dumps(stale_request_payload, ensure_ascii=False),
        )
        await redis.set(
            AgentDispatchService._state_key(stale_request_id),
            json.dumps(stale_state_payload, ensure_ascii=False),
        )
        await redis.rpush(AgentDispatchService._queue_key("agent-1"), stale_request_id)

        dispatch_module.connected_agents = {"agent-1": object()}
        started_requests: list[str | None] = []

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, message, timeout_seconds
            started_requests.append(request_id)
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "陈旧队列头清理测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            response = await AgentDispatchService.send_ai_analysis_message(
                redis,
                "agent-1",
                {"requestType": 6, "command": "run_ticket_ai_analysis"},
                request_id="dispatch-follower",
                timeout_seconds=30,
            )

            assert response.status_code == 200
            assert started_requests == ["dispatch-follower"]
            assert await redis.lindex(AgentDispatchService._queue_key("agent-1"), 0) is None
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())



def test_ai_analysis_dispatch_cleans_expired_queued_lease_head_before_request_timeout():
    """
    队列头仍在总超时内，但排队心跳租约已经过期时，应自动清理旧头并继续调度后续请求。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        stale_request_id = "dispatch-stale-lease-head"
        stale_message = {"requestType": 6, "command": "run_ticket_ai_analysis"}
        stale_request_payload = {
            "requestId": stale_request_id,
            "agentCode": "agent-1",
            "message": stale_message,
            "timeoutSeconds": 600,
            "createdAt": int(time.time()) - 5,
        }
        stale_state_payload = {
            "requestId": stale_request_id,
            "agentCode": "agent-1",
            "status": "queued",
            "timeoutSeconds": 600,
            "requestType": 6,
            "command": "run_ticket_ai_analysis",
            "updatedAt": int(time.time()) - 120,
            "queueLeaseUntil": int(time.time()) - 1,
        }
        await redis.set(
            AgentDispatchService._request_key(stale_request_id),
            json.dumps(stale_request_payload, ensure_ascii=False),
        )
        await redis.set(
            AgentDispatchService._state_key(stale_request_id),
            json.dumps(stale_state_payload, ensure_ascii=False),
        )
        await redis.rpush(AgentDispatchService._queue_key("agent-1"), stale_request_id)

        dispatch_module.connected_agents = {"agent-1": object()}
        started_requests: list[str | None] = []

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, message, timeout_seconds
            started_requests.append(request_id)
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "排队租约清理测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            response = await AgentDispatchService.send_ai_analysis_message(
                redis,
                "agent-1",
                {"requestType": 6, "command": "run_ticket_ai_analysis"},
                request_id="dispatch-follower-lease",
                timeout_seconds=30,
            )

            assert response.status_code == 200
            assert started_requests == ["dispatch-follower-lease"]
            assert await redis.lindex(AgentDispatchService._queue_key("agent-1"), 0) is None
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())


def test_ai_analysis_dispatch_reloads_cached_message_after_queue_wait():
    """
    排队阶段只保留轻量元数据时，拿到槽位后仍应从缓存恢复完整请求并转发给 Agent。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        dispatch_module.connected_agents = {"agent-1": object()}
        first_request_can_finish = asyncio.Event()
        received_payloads: list[str | None] = []

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, request_id, timeout_seconds
            received_payloads.append(message.get("extraPayload"))
            if len(received_payloads) == 1:
                await first_request_can_finish.wait()
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "缓存消息恢复测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            first_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {
                        "requestType": 6,
                        "command": "run_ticket_ai_analysis",
                        "extraPayload": "first-payload",
                    },
                    request_id="dispatch-reload-1",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.2)

            second_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {
                        "requestType": 6,
                        "command": "run_ticket_ai_analysis",
                        "extraPayload": "second-payload",
                    },
                    request_id="dispatch-reload-2",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.5)
            first_request_can_finish.set()

            first_response = await first_task
            second_response = await second_task

            assert first_response.status_code == 200
            assert second_response.status_code == 200
            assert received_payloads == ["first-payload", "second-payload"]
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())


def test_cleanup_orphan_active_leases_clears_all_agents_and_marks_state():
    """
    服务重启清理孤儿租约：应清空全部 Agent 的 active 租约并标记请求状态为失败。
    """
    import asyncio

    async def scenario():
        redis = MemoryRedis()
        # 模拟上次进程被杀遗留的两个 Agent 各自的租约
        await redis.hset("agent:ai_analysis:active:agent-1", "req-legacy-1", str(int(time.time()) + 3600))
        await redis.hset("agent:ai_analysis:active:agent-1", "req-legacy-2", str(int(time.time()) - 10))
        await redis.hset("agent:ai_analysis:active:agent-2", "req-legacy-3", str(int(time.time()) + 7200))

        removed = await AgentDispatchService.cleanup_orphan_active_leases(redis)

        assert removed == 3
        assert await redis.hgetall("agent:ai_analysis:active:agent-1") == {}
        assert await redis.hgetall("agent:ai_analysis:active:agent-2") == {}
        # 请求状态应被标记为 failed（reason=orphan-lease-cleanup-on-restart）
        state = await AgentDispatchService._load_json_cache(redis, AgentDispatchService._state_key("req-legacy-1"))
        assert state is not None
        assert state["status"] == "failed"
        assert state["reason"] == "orphan-lease-cleanup-on-restart"
        # 队列不受影响（清理只动 active 租约）
        assert await redis.lrange("agent:ai_analysis:queue:agent-1", 0, -1) == []

    asyncio.run(scenario())


def test_cleanup_orphan_active_leases_noop_when_empty():
    """无遗留租约时清理应返回 0 且不报错。"""
    import asyncio

    async def scenario():
        redis = MemoryRedis()
        removed = await AgentDispatchService.cleanup_orphan_active_leases(redis)
        assert removed == 0

    asyncio.run(scenario())


def test_cleanup_orphan_active_leases_recovers_queue_immediately():
    """
    回归场景（2026-09-08 10:35 OOM 重启）：重启后遗留租约占满槽位，重试请求被阻塞
    到旧租约自然过期。清理后重试请求应立即获得槽位。
    """

    async def scenario():
        redis = MemoryRedis()
        agent = "agent-1"
        # 重启前遗留的租约（远未过期）
        await redis.hset(f"agent:ai_analysis:active:{agent}", "req-old", str(int(time.time()) + 3600))
        # 重启后重试请求排在队列头（真实链路中 _cache_request 会先写入请求缓存）
        await redis.lpush(f"agent:ai_analysis:queue:{agent}", "req-new")
        await redis.set(
            AgentDispatchService._request_key("req-new"),
            json.dumps(
                {"message": {"requestType": 6, "command": "run_ticket_ai_analysis"}, "createdAt": int(time.time())}
            ),
            ex=86400,
        )

        # 清理遗留租约
        removed = await AgentDispatchService.cleanup_orphan_active_leases(redis)
        assert removed == 1

        # 清理后队列头请求应能立即准入
        admitted = await AgentDispatchService._try_admit_request(
            redis,
            agent_code=agent,
            request_id="req-new",
            message={"requestType": 6},
            max_concurrent_tasks=1,
            lease_seconds=3900,
        )
        assert admitted is True
        active = await redis.hgetall(f"agent:ai_analysis:active:{agent}")
        assert set(active.keys()) == {"req-new"}

    asyncio.run(scenario())


def test_ai_analysis_dispatch_fails_fast_when_agent_offline_at_submit():
    """
    提交时 Agent 已离线：应立即返回失败并带明确原因，不进入队列等待到总超时。
    回归场景（INC00001967826）：Agent 静默断连后任务排队空转约一小时才超时。
    """
    import asyncio

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        dispatch_module.connected_agents = {}
        try:
            response = await AgentDispatchService.send_ai_analysis_message(
                redis,
                "agent-offline",
                {"requestType": 6, "command": "run_ticket_ai_analysis"},
                request_id="dispatch-offline-1",
                timeout_seconds=30,
            )
            assert response.status_code == AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value
            assert "当前离线" in str(response.message)
            # 不应写入请求缓存和队列
            assert await redis.get(AgentDispatchService._request_key("dispatch-offline-1")) is None
            assert await redis.lrange("agent:ai_analysis:queue:agent-offline", 0, -1) == []
        finally:
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())


def test_ai_analysis_dispatch_fails_fast_when_agent_goes_offline_while_queued():
    """
    排队期间 Agent 掉线：等待循环应立即失败并清理队列，不再空转到总超时。
    """

    async def scenario():
        redis = MemoryRedis()
        await redis.set("sys_config:ticket.ai.agent.maxConcurrentTasks", "1")

        dispatch_module.connected_agents = {"agent-1": object()}
        first_request_can_finish = asyncio.Event()

        async def fake_agent_send_message(agent_code, message, request_id=None, timeout_seconds=None):
            del agent_code, message, timeout_seconds
            await first_request_can_finish.wait()
            return HandleResponse(
                status_code=200,
                response=AgentResponseWebUI(
                    request_type=6,
                    success=True,
                    message="ok",
                    result={"analysis_result": {"root_cause": "排队掉线测试"}},
                ),
                message="操作成功",
            )

        original_sender = dispatch_module.agent_send_message
        dispatch_module.agent_send_message = fake_agent_send_message
        try:
            first_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-queued-offline-1",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.2)

            second_task = asyncio.create_task(
                AgentDispatchService.send_ai_analysis_message(
                    redis,
                    "agent-1",
                    {"requestType": 6, "command": "run_ticket_ai_analysis"},
                    request_id="dispatch-queued-offline-2",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.2)
            # 排队中的第二个请求等待期间 Agent 掉线，应快速失败
            dispatch_module.connected_agents = {}
            second_response = await second_task
            assert second_response.status_code == AgentResponseEnum.WEBSOCKET_NOT_CONNECTED.value
            assert "排队期间连接断开" in str(second_response.message)
            # 队列中不应残留该请求
            assert await redis.lrange("agent:ai_analysis:queue:agent-1", 0, -1) == []

            first_request_can_finish.set()
            first_response = await first_task
            assert first_response.status_code == 200
        finally:
            dispatch_module.agent_send_message = original_sender
            dispatch_module.connected_agents = {}

    asyncio.run(scenario())
