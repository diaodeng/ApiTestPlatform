import json

from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_field_mapping_service import ModuleMappingResult


def test_normalize_pos_or_sco_no_rejects_currency_and_thousands_values():
    """金额及千分位文本不能被截取为机台编号。"""
    assert TicketLightAiService._normalize_pos_or_sco_no("$44,510.00") is None
    assert TicketLightAiService._normalize_pos_or_sco_no("44,510.00") is None
    assert TicketLightAiService._normalize_pos_or_sco_no("POS #2") == 2


def test_sync_extract_prefers_explicit_pos_semantics_over_model_amount():
    """原文明确为 #2 POS 时，应覆盖模型把金额误填为 44 的结果。"""
    pos_no, sco_no, warnings = TicketLightAiService._normalize_sync_extract_machine_numbers(
        {"posNo": "$44,510.00", "scoNo": None},
        "",
        "Store reported 2026-08-20 21:56:52 #2 POS, $44,510.00 個袋是人工輸入",
        {},
    )
    assert pos_no == 2
    assert sco_no is None
    assert warnings == ["模型POS值$44,510.00无效，已采用原文明确POS=2"]


def test_module_mapping_result_is_json_safe_for_automation_detail():
    """自动化识别详情不得携带不可序列化的模块映射 dataclass。"""
    result = ModuleMappingResult(
        mapping_matched=True,
        mapped_module_code="pos_admin",
        resolved_module_id=100,
        resolved_module_code="pos_admin",
        resolved_module_name="POS-管理端",
        matched_by="mapping_moduleCode",
    )
    safe = TicketSyncAutomationService._json_safe_detected({"moduleMappingResult": result, "posNo": 2})
    assert safe["moduleMappingResult"]["resolvedModuleId"] == 100
    json.dumps(safe, ensure_ascii=False)


def test_sync_ai_field_service_keeps_store_id_as_text():
    """同步 AI 回填摘要中的门店编号应保持字符串，兼容非纯数字编码。"""
    from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
    from modules.ticket.service.sync.ticket_sync_ai_field_service import TicketSyncAiFieldService

    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "T-1",
            "source": {"system": "test"},
            "description": "POS 2",
            "logPullConfig": {},
        }
    )
    updated, applied = TicketSyncAiFieldService.apply_extract_to_sync_object(
        sync_object,
        {"posNo": 2, "store": "SAP001", "logDate": "2026-08-20"},
    )
    assert updated.log_pull_config["storeId"] == "SAP001"
    assert applied["logPullConfig"]["storeId"] == "SAP001"
