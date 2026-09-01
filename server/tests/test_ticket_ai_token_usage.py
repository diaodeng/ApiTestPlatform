from types import SimpleNamespace
from unittest.mock import Mock

from module_admin.service.ai_task_execution_service import AiTaskExecutionService
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.core.ticket_read_service import TicketReadService


def test_extract_token_usage_payload_prefers_nested_usage():
    """应能从嵌套结构中提取原始 Token 用量。"""
    payload = TicketAiAnalysisService._extract_token_usage_payload(
        {"result": {"usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}}}
    )

    assert payload == {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46}


def test_normalize_token_usage_keeps_total_only_without_guessing_split():
    """只有总量时不估算输入/输出，只保留 total。"""
    normalized = TicketAiAnalysisService._normalize_token_usage({"total_tokens": 88})

    assert normalized == {
        "input_token_count": None,
        "output_token_count": None,
        "total_token_count": 88,
    }


def test_normalize_token_usage_sums_prompt_and_completion_when_total_missing():
    """有明确 prompt/completion 时，可安全推导总量。"""
    normalized = TicketAiAnalysisService._normalize_token_usage(
        {"prompt_tokens": 21, "completion_tokens": 34}
    )

    assert normalized == {
        "input_token_count": 21,
        "output_token_count": 34,
        "total_token_count": 55,
    }


def test_ticket_read_summary_includes_ai_token_summary(monkeypatch):
    """工单轻量概览应挂载 AI Token 汇总。"""
    ticket = SimpleNamespace(ticket_id=1)
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketDao.get_ticket_by_id',
        lambda db, ticket_id: ticket,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.CamelCaseUtil.transform_result',
        lambda obj: {"ticketId": 1, "projectName": "示例项目", "merchantName": "示例项目"},
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketVersionService.attach_ticket_version_labels',
        lambda db, rows: None,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketReadService._attach_issue',
        lambda db, data, current_ticket: None,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketReadService._attach_relation_codes',
        lambda db, data, current_ticket: None,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketLogPullService.get_latest_summary',
        lambda db, ticket_id: None,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketAiAnalysisService.get_latest_summary',
        lambda db, ticket_id: None,
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketAiDao.get_ticket_token_summary',
        lambda db, ticket_id: {
            "input_token_count": 11,
            "output_token_count": 22,
            "total_token_count": 33,
            "task_count": 4,
            "success_task_count": 3,
        },
    )
    monkeypatch.setattr(
        'modules.ticket.service.core.ticket_read_service.TicketPromptService.resolve_prompt_layers',
        lambda db, current_ticket: {},
    )

    result = TicketReadService.get_summary(Mock(), 1)

    assert result is not None
    assert result.ai_token_summary is not None
    assert result.ai_token_summary.total_token_count == 33
    assert result.ai_token_summary.task_count == 4


def test_ai_task_execution_service_prefers_total_tokens():
    """审计列表摘要应优先使用原始 total_tokens。"""
    execution = SimpleNamespace(token_usage={"total_tokens": 99})

    result = AiTaskExecutionService.build_ai_task_execution_model(execution)

    assert result.total_token_count == 99


def test_ai_task_execution_service_can_sum_input_and_output():
    """审计列表摘要在缺少 total 时可按输入/输出求和。"""
    execution = SimpleNamespace(token_usage={"prompt_tokens": 40, "completion_tokens": 60})

    result = AiTaskExecutionService.build_ai_task_execution_model(execution)

    assert result.total_token_count == 100


def test_agent_response_webui_preserves_token_usage_from_client():
    """客户端回传的 token_usage 应被 AgentResponseWebUI 保留，不再被 Pydantic 静默丢弃。"""
    from module_qtr.service.agent_service import AgentResponseWebUI

    client_response = {
        "request_type": 6,
        "status": "success",
        "success": True,
        "message": "AI 分析完成",
        "token_usage": {
            "input_tokens": 13273,
            "output_tokens": 25,
            "cached_input_tokens": 2048,
            "total_tokens": 13298,
        },
        "result": {
            "analysis_result": {"ticket_id": "1"},
        },
    }

    response = AgentResponseWebUI(**client_response)

    assert response.token_usage is not None
    assert response.token_usage["input_tokens"] == 13273
    assert response.token_usage["total_tokens"] == 13298


def test_transport_payload_json_roundtrip_keeps_token_usage():
    """Redis/HTTP 传输序列化往返（camelCase 别名）后 token_usage 仍应保留。"""
    import json

    from module_qtr.service.agent_service import AgentResponseWebUI, HandleResponse

    payload = json.dumps(
        {
            "statusCode": 200,
            "response": {
                "requestType": 6,
                "status": "success",
                "success": True,
                "message": "AI 分析完成",
                "tokenUsage": {
                    "inputTokens": 13273,
                    "outputTokens": 25,
                    "cachedInputTokens": 2048,
                    "totalTokens": 13298,
                },
                "result": {"analysis_result": {"ticket_id": "1"}},
            },
            "message": "操作成功",
        },
        ensure_ascii=False,
    )

    response = HandleResponse.validate_transport_payload(payload)

    assert isinstance(response.response, AgentResponseWebUI)
    assert response.response.token_usage is not None
    assert response.response.token_usage["inputTokens"] == 13273


def test_server_extract_and_normalize_token_usage_from_result():
    """服务端应能从 result.token_usage 递归提取并归一化为入库字段。"""
    result_payload = {
        "analysis_result": {"ticket_id": "1"},
        "token_usage": {
            "input_tokens": 13273,
            "output_tokens": 25,
            "cached_input_tokens": 2048,
            "total_tokens": 13298,
        },
    }

    extracted = TicketAiAnalysisService._extract_token_usage_payload(result_payload)
    normalized = TicketAiAnalysisService._normalize_token_usage(extracted)

    assert normalized is not None
    assert normalized["input_token_count"] == 13273
    assert normalized["output_token_count"] == 25
    assert normalized["total_token_count"] == 13298
