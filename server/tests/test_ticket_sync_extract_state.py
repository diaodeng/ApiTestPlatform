"""统一提取指纹和自动化输入服务回归测试。"""

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_automation_input_service import TicketSyncAutomationInputService
from modules.ticket.service.sync.ticket_sync_extract_state_service import TicketSyncExtractStateService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService


def test_extract_source_hash_ignores_comments_and_sync_noise():
    """评论、记录链接和同步时间变化不应触发统一提取。"""
    _, first_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述",
        raw_payload={
            "ticketPos": "2",
            "comments": [{"text": "第一次"}],
            "recordUrl": "https://one.example",
            "updatedAt": "2026-08-24T10:00:00",
        },
    )
    _, second_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述",
        raw_payload={
            "ticketPos": "2",
            "comments": [{"text": "第二次"}],
            "recordUrl": "https://two.example",
            "updatedAt": "2026-08-24T11:00:00",
        },
    )
    assert first_hash == second_hash


def test_extract_source_hash_changes_when_description_or_business_field_changes():
    """描述和 POS 等业务字段变化必须触发重新提取。"""
    _, first_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述A",
        raw_payload={},
        source_fields={"posNo": 2, "store": "1272"},
    )
    _, changed_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述B",
        raw_payload={},
        source_fields={"posNo": 3, "store": "1272"},
    )
    assert first_hash != changed_hash


def test_extract_source_hash_excludes_ai_and_automation_state_but_keeps_source_store_code():
    """来源门店变化触发提取，AI结果和自动化状态变化不触发提取。"""
    _, first_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述",
        raw_payload={"sourceStoreCode": "ORG-001", "ai_sync_extract": {"result": {"store": "ORG-001"}}},
        source_fields={"sourceStoreCode": "ORG-001"},
    )
    _, second_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述",
        raw_payload={"sourceStoreCode": "ORG-002", "ai_sync_extract": {"result": {"store": "ORG-002"}}},
        source_fields={"sourceStoreCode": "ORG-002"},
    )
    assert first_hash != second_hash

    _, state_changed_hash = TicketSyncExtractStateService.build_source_hash(
        title="标题",
        description="描述",
        raw_payload={"sourceStoreCode": "ORG-001", "ai_sync_extract": {"result": {"store": "OTHER"}}},
        source_fields={"sourceStoreCode": "ORG-001"},
    )
    assert first_hash == state_changed_hash


def test_extract_cache_requires_matching_source_and_prompt_hash():
    """只有成功且双指纹一致时才复用缓存。"""
    state = {
        "result": {"posNo": 2},
        "meta": {"success": True, "sourceHash": "source", "promptHash": "prompt"},
    }
    assert TicketSyncExtractStateService.get_cache_hit(state, source_hash="source", prompt_hash="prompt") == {
        "posNo": 2
    }
    assert TicketSyncExtractStateService.get_cache_hit(state, source_hash="changed", prompt_hash="prompt") is None
    assert TicketSyncExtractStateService.get_cache_hit(state, source_hash="source", prompt_hash="changed") is None


def test_resolve_modify_time_handles_missing_or_null_log_pull_hints():
    """日志 hints 缺失或为 None 时，日期回退不应阻断主同步。"""
    for extra_data in ({}, {"log_pull_hints": None}, {"log_pull_hints": {}}):
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "INC-HINTS",
                "source": {"system": "test"},
                "extraData": extra_data,
            }
        )
        assert TicketSyncPayloadService.resolve_auto_log_pull_modify_time(
            sync_object=sync_object,
            log_pull_payload={},
        ) == ""

    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-HINTS-DATE",
            "source": {"system": "test"},
            "extraData": {"log_pull_hints": {"modifyTime": "2026-08-20"}},
        }
    )
    assert TicketSyncPayloadService.resolve_auto_log_pull_modify_time(
        sync_object=sync_object,
        log_pull_payload={},
    ) == "2026-08-20"


def test_automation_runtime_keeps_source_store_and_selects_ai_store_consistently():
    """自动化参数应保留来源编码，并按统一规则选择最终 storeId。"""
    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-2",
            "source": {"system": "test"},
            "rawPayload": {"sourceStoreCode": "ORG-552283"},
            "logPullConfig": {"sourceStoreCode": "ORG-552283", "storeId": "OLD"},
        }
    )
    runtime = TicketSyncAutomationInputService.resolve_runtime_config(
        config={},
        automation=None,
        sync_object=sync_object,
        detected={},
        ticket_id=2,
        ticket_extra_data={
            "ai_sync_extract": {
                "result": {"store": "552283"},
                "meta": {"success": True},
            }
        },
    )
    assert runtime["sourceStoreCode"] == "ORG-552283"
    assert runtime["storeId"] == "552283"
    assert runtime["storeSelectionReason"] == "ai_value_contained"


def test_automation_runtime_keeps_detected_mapped_store_id_for_sap_source_code():
    """外部 SAP 门店编码已映射为 org_no 时，运行参数必须使用映射后的门店。"""
    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-STORE-MAP",
            "source": {"system": "test"},
            "rawPayload": {"ticketStore": "1272"},
            "logPullConfig": {"sourceStoreCode": "1272", "storeId": "1272"},
        }
    )
    runtime = TicketSyncAutomationInputService.resolve_runtime_config(
        config={},
        automation=None,
        sync_object=sync_object,
        detected={"vendorId": 11, "storeId": "552283", "storeName": "7E-28-36 NASSAU ST"},
        ticket_id=3,
        ticket_extra_data={
            "ai_sync_extract": {
                "result": {"store": "1272"},
                "meta": {"success": True},
            }
        },
    )
    assert runtime["sourceStoreCode"] == "1272"
    assert runtime["storeId"] == "552283"
    assert runtime["storeSelectionReason"] == "detected_mapped_store_id"


def test_automation_runtime_stops_on_ambiguous_store_mapping_and_keeps_candidates():
    """同一商家外部门店编码命中多个 org_no 时不得静默选择门店。"""
    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-STORE-AMBIGUOUS",
            "source": {"system": "test"},
            "rawPayload": {"ticketStore": "1272"},
            "logPullConfig": {"sourceStoreCode": "1272", "storeId": "552283"},
        }
    )
    candidates = [
        {"orgNo": "552283", "orgName": "门店A", "sapOrgNo": "1272"},
        {"orgNo": "546619", "orgName": "门店B", "sapOrgNo": "1272"},
    ]
    runtime = TicketSyncAutomationInputService.resolve_runtime_config(
        config={"logPullDefaults": {"storeId": "546619"}},
        automation=None,
        sync_object=sync_object,
        detected={
            "vendorId": 11,
            "storeId": "",
            "storeMappingAmbiguous": True,
            "storeMappingCandidates": candidates,
        },
        ticket_id=4,
        ticket_extra_data={
            "log_pull_hints": {"storeId": "552283"},
            "ai_sync_extract": {
                "result": {"store": "546619"},
                "meta": {"success": True},
            },
        },
    )
    assert runtime["storeMappingAmbiguous"] is True
    assert runtime["storeMappingCandidates"] == candidates
    assert runtime["storeSelectionReason"] == "ambiguous_external_store_mapping"
    assert runtime.get("storeId", "") == ""


def test_automation_runtime_reads_hints_and_applies_task_values():
    """自动化输入统一读取已落库 hints，并由任务级参数覆盖历史值。"""
    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-1",
            "source": {"system": "test"},
            "description": "POS 2",
            "logPullConfig": {"storeId": "old-store", "posNo": 4},
        }
    )
    runtime = TicketSyncAutomationInputService.resolve_runtime_config(
        config={"logPullDefaults": {"vendorId": 11, "storeId": "default", "posNo": 9}},
        automation=None,
        sync_object=sync_object,
        detected={"vendorId": 11, "storeId": "detected", "posNo": 3},
        ticket_id=1,
        ticket_extra_data={
            "log_pull_hints": {"vendorId": 11, "storeId": "552283", "posNo": 2, "modifyTime": "2026-08-20"}
        },
    )
    assert runtime["storeId"] == "old-store"
    assert runtime["posNo"] == 4
    assert runtime["modifyTime"] == "2026-08-20"


def test_automation_runtime_propagates_default_log_pull_environment():
    """自动拉日志默认环境应从 logPullDefaults 传入最终运行参数。"""
    sync_object = TicketExternalSyncUpsertModel.model_validate(
        {
            "ticketNo": "INC-ENV",
            "source": {"system": "test"},
            "description": "POS 2",
        }
    )
    runtime = TicketSyncAutomationInputService.resolve_runtime_config(
        config={"logPullDefaults": {"environment": "PROD:PROD"}},
        automation=None,
        sync_object=sync_object,
        detected={"vendorId": 11, "storeId": "546619", "posNo": 2},
        ticket_id=5,
        ticket_extra_data={"log_pull_hints": {"modifyTime": "2026-08-20"}},
    )
    assert runtime["environment"] == "PROD:PROD"
