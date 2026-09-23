"""Agent WebSocket 连接会话归属和响应 Future 清理测试。"""

import asyncio

import pytest

import module_qtr.controller.agent_controller as controller


class FakeWebSocket:
    """提供连接管理器所需的最小 WebSocket 行为。"""

    def __init__(self):
        self.accepted = False
        self.closed = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=None, reason=None):
        self.closed.append((code, reason))


@pytest.fixture(autouse=True)
def reset_connection_state():
    """每个测试前后清理全局连接和 Future 注册表。"""
    controller.agent_connection_sessions.clear()
    controller.agents.clear()
    controller.agent_loops.clear()
    controller.agent_sessions.clear()
    controller.response_futures.clear()
    yield
    controller.agent_connection_sessions.clear()
    controller.agents.clear()
    controller.agent_loops.clear()
    controller.agent_sessions.clear()
    controller.response_futures.clear()


def test_old_connection_cannot_disconnect_new_session():
    """新连接接管后，旧连接 finally 不能移除新连接。"""
    async def scenario():
        manager = controller.ConnectionManager()
        old_websocket = FakeWebSocket()
        new_websocket = FakeWebSocket()

        old_session = await manager.connect("agent-session", old_websocket)
        new_session = await manager.connect("agent-session", new_websocket)

        await manager.disconnect(
            "agent-session",
            close_code=1000,
            session_id=old_session,
            websocket=old_websocket,
        )

        current = controller.agent_connection_sessions["agent-session"]
        assert current["session_id"] == new_session
        assert current["websocket"] is new_websocket
        assert controller.agents["agent-session"] is new_websocket
        assert old_websocket.closed, "新连接建立时旧 WebSocket 应收到关闭通知"

        await manager.disconnect(
            "agent-session",
            close_code=1000,
            session_id=new_session,
            websocket=new_websocket,
        )
        assert "agent-session" not in controller.agent_connection_sessions

    asyncio.run(scenario())


def test_response_future_requires_matching_agent_and_session():
    """响应 Future 必须同时匹配 Agent 编码和连接 session。"""
    request_state = {"agent_code": "agent-a", "session_id": "session-a"}

    assert controller._response_future_matches_connection(request_state, "agent-a", "session-a")
    assert not controller._response_future_matches_connection(request_state, "agent-a", "session-b")
    assert not controller._response_future_matches_connection(request_state, "agent-b", "session-a")


def test_discard_response_future_cancels_waiter_and_removes_state():
    """异常分片被丢弃时，等待方 Future 必须取消且注册表必须清理。"""
    async def scenario():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        controller.response_futures["request-invalid"] = {
            "future": future,
            "loop": loop,
            "agent_code": "agent-a",
            "session_id": "session-a",
        }

        controller._discard_response_future("request-invalid", "测试错误分片")
        await asyncio.sleep(0)

        assert future.cancelled()
        assert "request-invalid" not in controller.response_futures

    asyncio.run(scenario())
