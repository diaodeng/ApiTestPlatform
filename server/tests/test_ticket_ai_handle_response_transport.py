import asyncio
import json
from unittest.mock import patch

from config.cache_backend import MemoryRedis
from module_qtr.service.agent_dispatch_service import AgentDispatchService
from module_qtr.service.agent_service import AgentResponseWebUI, HandleResponse
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


def test_handle_response_validate_transport_payload_supports_ai_analysis_json():
    """HTTP/Redis 传输后的 AI 分析响应 JSON 应能恢复为 HandleResponse 模型。"""
    payload = json.dumps(
        {
            "statusCode": 200,
            "response": {
                "requestType": 6,
                "command": "run_ticket_ai_analysis",
                "status": "failed",
                "success": False,
                "message": "PowerShell doesn't support heredoc with <<",
                "result": {
                    "stderr_context": "ParserError",
                    "analysis_result": None,
                },
            },
            "message": "操作成功",
        },
        ensure_ascii=False,
    )

    response = HandleResponse.validate_transport_payload(payload)

    assert response.status_code == 200
    assert isinstance(response.response, AgentResponseWebUI)
    assert response.response.success is False
    assert response.response.message == "PowerShell doesn't support heredoc with <<"
    assert response.response.result["stderr_context"] == "ParserError"



def test_ticket_ai_gateway_parses_transport_payload_without_json_validator_error():
    """工单 AI 内部网关应先解析 JSON，再按 Python 对象校验，避免 Pydantic JSON 校验误报。"""

    response_text = json.dumps(
        {
            "statusCode": 200,
            "response": {
                "requestType": 6,
                "command": "run_ticket_ai_analysis",
                "status": "failed",
                "success": False,
                "message": "PowerShell doesn't support heredoc with <<",
                "result": {
                    "stderr_context": "ParserError",
                },
            },
            "message": "操作成功",
        },
        ensure_ascii=False,
    )

    class FakeResponse:
        """模拟 httpx 响应对象。"""

        def __init__(self, text: str):
            """保存响应文本。"""
            self.text = text

        def raise_for_status(self) -> None:
            """测试场景中不抛出 HTTP 错误。"""
            return None

    class FakeClient:
        """模拟 httpx.Client 上下文。"""

        def __init__(self, *args, **kwargs):
            """忽略测试中的初始化参数。"""
            del args, kwargs

        def __enter__(self):
            """进入上下文时返回自身。"""
            return self

        def __exit__(self, exc_type, exc, tb):
            """退出上下文时不吞掉异常。"""
            del exc_type, exc, tb
            return False

        def post(self, url: str, json: dict | None = None):
            """返回固定的 AI 分析网关响应。"""
            del url, json
            return FakeResponse(response_text)

    with patch("modules.ticket.service.ai.ticket_ai_analysis_service.httpx.Client", FakeClient):
        response = TicketAiAnalysisService._send_agent_request_via_gateway(
            agent_code="agent-1",
            request_payload={"requestType": 6, "command": "run_ticket_ai_analysis"},
            request_id="ticket-ai-analysis:test",
            timeout_seconds=30,
        )

    assert response.status_code == 200
    assert isinstance(response.response, AgentResponseWebUI)
    assert response.response.success is False
    assert response.response.result["stderr_context"] == "ParserError"



def test_agent_dispatch_service_load_cached_result_supports_transport_json_payload():
    """Redis 中缓存的 AI 分析响应 JSON 应能恢复为 HandleResponse，避免重复请求命中旧校验错误。"""

    async def scenario():
        redis = MemoryRedis()
        await redis.set(
            AgentDispatchService._result_key("cached-ai-analysis"),
            json.dumps(
                {
                    "statusCode": 200,
                    "response": {
                        "requestType": 6,
                        "status": "failed",
                        "success": False,
                        "message": "PowerShell doesn't support heredoc with <<",
                        "result": {"stderr_context": "ParserError"},
                    },
                    "message": "操作成功",
                },
                ensure_ascii=False,
            ),
        )

        response = await AgentDispatchService._load_cached_result(redis, "cached-ai-analysis")

        assert response is not None
        assert response.status_code == 200
        assert isinstance(response.response, AgentResponseWebUI)
        assert response.response.result["stderr_context"] == "ParserError"

    asyncio.run(scenario())
