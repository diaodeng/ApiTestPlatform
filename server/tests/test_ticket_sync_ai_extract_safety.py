import json
from datetime import datetime

from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_field_mapping_service import ModuleMappingResult
from modules.ticket.util.ticket_store_resolution_util import TicketStoreResolutionUtil


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



def test_automation_step_detail_converts_datetime_to_json_value():
    """自动化步骤审计中的时间对象必须转换后才能写入 JSON 扩展字段。"""
    meta: dict = {}
    TicketSyncAutomationService.mark_automation_step(
        meta,
        step="log_pull",
        status="submitted",
        detail={"submittedAt": datetime(2026, 8, 25, 14, 2, 55)},
    )
    detail = meta["sync_state"]["automation"]["steps"]["log_pull"]["detail"]
    assert detail["submittedAt"] == "2026-08-25T14:02:55"
    json.dumps(meta, ensure_ascii=False)
    """来源编码只读，AI 仅在相等或被来源编码包含时成为最终门店。"""
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="ORG-552283",
        ai_store="552283",
        existing_store_id="OLD",
    ) == ("552283", "ai_value_contained")
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="552283",
        ai_store="552283",
        existing_store_id="OLD",
    ) == ("552283", "ai_exact_match")
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="552283",
        ai_store="778899",
        existing_store_id="OLD",
    ) == ("552283", "fallback_source_store_code")
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="552283",
        ai_store="",
        existing_store_id="OLD",
    ) == ("552283", "fallback_source_store_code")


def test_store_resolution_without_source_allows_ai_to_replace_existing_store():
    """没有外部来源编码时，有效 AI 门店可以替换旧值。"""
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="",
        ai_store="NEW",
        existing_store_id="OLD",
    ) == ("NEW", "ai_without_source")


def test_store_resolution_keeps_existing_value_when_both_sources_are_empty():
    """没有来源编码和有效 AI 值时保留已有日志门店。"""
    assert TicketStoreResolutionUtil.select_store_id(
        source_store_code="",
        ai_store="",
        existing_store_id="OLD",
    ) == ("OLD", "keep_existing_store_id")


def test_sync_ai_field_service_uses_source_store_rule_and_never_rewrites_source_code():
    """AI 新值按来源编码规则更新 storeId，但不反写 sourceStoreCode。"""
    from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
    from modules.ticket.service.sync.ticket_sync_ai_field_service import TicketSyncAiFieldService

    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "T-2",
            "source": {"system": "test"},
            "description": "门店变更",
            "rawPayload": {"sourceStoreCode": "ORG-552283"},
            "logPullConfig": {"sourceStoreCode": "ORG-552283", "storeId": "OLD"},
        }
    )
    updated, applied = TicketSyncAiFieldService.apply_extract_to_sync_object(
        sync_object,
        {"store": "552283"},
    )
    assert updated.log_pull_config["sourceStoreCode"] == "ORG-552283"
    assert updated.log_pull_config["storeId"] == "552283"
    assert updated.extra_data["_ai_extract"]["store"] == "552283"
    assert applied["logPullConfig"]["selectionReason"] == "ai_value_contained"

    fallback, fallback_meta = TicketSyncAiFieldService.apply_extract_to_sync_object(
        updated,
        {"store": "OTHER"},
    )
    assert fallback.log_pull_config["sourceStoreCode"] == "ORG-552283"
    assert fallback.log_pull_config["storeId"] == "ORG-552283"
    assert fallback_meta["logPullConfig"]["selectionReason"] == "fallback_source_store_code"
    assert fallback.extra_data["_ai_extract"]["store"] == "ORG-552283"


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
