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
