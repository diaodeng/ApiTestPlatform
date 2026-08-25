import asyncio

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
