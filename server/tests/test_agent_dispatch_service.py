import asyncio
import json
import time

from config.cache_backend import MemoryRedis
from module_qtr.service import agent_dispatch_service as dispatch_module
from module_qtr.service.agent_dispatch_service import AgentDispatchService
from module_qtr.service.agent_service import AgentResponseWebUI, HandleResponse


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
