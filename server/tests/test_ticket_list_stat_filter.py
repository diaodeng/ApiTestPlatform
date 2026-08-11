from modules.ticket.entity.vo.ticket_vo import TicketQueryModel
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService


def _stat_options():
    """构造根因分类和解决方式枚举，用于验证编码与显示名兼容。"""
    return {
        "rootCauseTypes": [
            {"value": "code_defect", "label": "代码缺陷"},
            {"value": "config_error", "label": "配置错误"},
        ],
        "solutionTypes": [
            {"value": "code_fix", "label": "代码修复"},
            {"value": "config_fix", "label": "配置修复"},
        ],
        "resolutions": [{"value": "fixed", "label": "已修复", "isProblem": True}],
        "issueTypes": [],
        "problemPatterns": [],
    }


def test_light_ai_classification_uses_stat_option_value_for_root_and_solution():
    """AI 分类归一化应把根因分类和解决方式写成编码，避免新数据继续写中文标签。"""
    result = TicketLightAiService._normalize_structured_classification_result(
        {
            "rootCauseType": "代码缺陷",
            "solutionType": "代码修复",
            "resolutionName": "已修复",
        },
        response_text="{}",
        stat_options=_stat_options(),
    )

    assert result["rootCauseType"] == "code_defect"
    assert result["solutionType"] == "code_fix"
    assert result["resolutionCode"] == "fixed"
    assert result["resolutionName"] == "已修复"


def test_ticket_list_filter_expands_stat_values_to_labels(monkeypatch):
    """工单列表筛选应把编码扩展为编码和中文标签，兼容历史中文入库数据。"""
    monkeypatch.setattr(
        TicketSyncConfigService,
        "get_ticket_stat_classification_options",
        staticmethod(lambda query_db: _stat_options()),
    )
    query = TicketQueryModel(rootCauseTypes="code_defect", solutionTypes="code_fix")

    expanded_query = TicketService._build_ticket_list_filter_query(None, query)

    assert expanded_query.root_cause_types == "code_defect,代码缺陷"
    assert expanded_query.solution_types == "code_fix,代码修复"
