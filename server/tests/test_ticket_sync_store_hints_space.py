"""日志拉取 hints 门店编码空间测试。

背景（INC00002013662）：resolve_store_by_external_value 匹配失败时会原样返回外部门店
编码（store_code 空间），旧逻辑无条件把它写进 log_pull_hints.storeId，导致 web 弹窗
回显把 store_code 当 org_no 提交。修复后 detect_fields 输出 storeMappingMatched 标记，
refresh_log_pull_hints 按标记决定写入/清除，保证 hints.storeId 恒为 org_no 空间或缺失。
"""
import unittest
from types import SimpleNamespace

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_sync_automation_service import (
    TicketSyncAutomationService,
)
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService


class _EmptyQuery:
    """空查询桩，避免测试触发数据库访问。"""

    def filter(self, *args, **kwargs):
        return self

    def first(self, *args, **kwargs):
        return None


class StoreHintsSpaceTests(unittest.TestCase):
    """log_pull_hints.storeId 的编码空间防护测试。"""

    def _build_sync_object(self, store_code: str = "215087") -> TicketExternalSyncUpsertModel:
        return TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "INC-TEST-STORE-SPACE",
                "source": {"system": "test"},
                "description": "描述",
                "rawPayload": {"fields": {"(IT)StoreCode": [{"text": store_code, "type": "text"}]}},
            }
        )

    def _build_flat_sync_object(self, store_code: str = "215087") -> TicketExternalSyncUpsertModel:
        """构造顶层携带 ticketStore 的同步对象（resolve_source_store_code 的读取口径）。"""
        return TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "INC-TEST-STORE-SPACE",
                "source": {"system": "test"},
                "description": "描述",
                "rawPayload": {"ticketStore": store_code},
            }
        )

    def test_matched_store_id_is_written(self):
        """匹配成功（storeMappingMatched=True）时 org_no 正常写入 hints。"""
        sync_object = self._build_sync_object()
        extra_data = {"log_pull_hints": {"vendorId": 5, "sourceStoreCode": "215087"}}

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={
                "vendorId": 5,
                "storeId": "333",
                "storeMappingMatched": True,
            },
            incoming_project_value=False,
        )

        self.assertEqual(hints["storeId"], "333")
        self.assertEqual(hints["sourceStoreCode"], "215087")

    def test_unmatched_source_code_is_not_written_and_clears_stale_store_id(self):
        """匹配失败时原始 store_code 不写入 hints，且清除旧 storeId 防止回显串店。"""
        sync_object = self._build_flat_sync_object(store_code="999999")
        extra_data = {
            "log_pull_hints": {
                "vendorId": 5,
                "storeId": "188",
                "sourceStoreCode": "215087",
            }
        }

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={
                "vendorId": 5,
                # resolve_store_by_external_value 失败时原样透传本次源编码
                "storeId": "999999",
                "storeMappingMatched": False,
            },
            incoming_project_value=False,
        )

        self.assertNotIn("storeId", hints)
        self.assertNotIn("store_id", hints)
        self.assertEqual(hints["sourceStoreCode"], "999999")
        self.assertEqual(hints["vendorId"], 5)

    def test_hints_fallback_org_no_is_kept_when_source_has_no_store_code(self):
        """本次同步未携带门店字段时（detected.storeId 来自旧 hints 回填），保留旧 org_no。"""
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "INC-TEST-STORE-SPACE",
                "source": {"system": "test"},
                "description": "描述",
            }
        )
        extra_data = {"log_pull_hints": {"vendorId": 5, "storeId": "333"}}

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={"vendorId": 5, "storeId": "333", "storeMappingMatched": False},
            incoming_project_value=False,
        )

        self.assertEqual(hints["storeId"], "333")

    def test_missing_flag_keeps_legacy_write_behavior(self):
        """detected 缺失 storeMappingMatched 键（旧调用方）时维持旧的写入行为。"""
        sync_object = self._build_sync_object()
        extra_data = {}

        hints = TicketSyncPayloadService.refresh_log_pull_hints(
            extra_data=extra_data,
            sync_object=sync_object,
            detected={"vendorId": 5, "storeId": "188"},
            incoming_project_value=False,
        )

        self.assertEqual(hints["storeId"], "188")

    def test_detect_fields_marks_store_mapping_unmatched_on_passthrough(self):
        """商家无法解析时门店编码走透传分支：storeId=原值 且 storeMappingMatched=False。"""
        sync_object = SimpleNamespace(
            ticket_no="INC-TEST-STORE-SPACE",
            title="标题",
            description="描述",
            raw_payload={"ticketStore": "215087"},
            extra_data={},
            project_code="",
            project_id=None,
            project_name="",
            module_id=None,
            module_code="",
            module_name="",
            merchant_name="",
            status="",
            current_assignee_id=None,
            current_assignee_name="",
            current_assignee_email="",
            reporter_name="",
            reporter_email="",
            internal_owner_name="",
            internal_owner_id=None,
            first_line_assignee_name="",
            first_line_assignee_id=None,
            root_cause=None,
            solution=None,
            log_pull_config={},
            detected_version_key=None,
            detected_affected_version_key=None,
            processed_at=None,
            submit_time=None,
        )

        detected = TicketSyncAutomationService.detect_fields(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            sync_object=sync_object,
            config={
                "projectMappings": [],
                "moduleMappings": [],
                "vendorMappings": [],
                "statusMappings": [],
                "assigneeMappings": [],
                "posPatterns": [],
                "scoPatterns": [],
                "versionPatterns": [],
            },
            apply_external_mappings=True,
        )

        self.assertEqual(detected["storeId"], "215087")
        self.assertFalse(detected["storeMappingMatched"])
        self.assertEqual(detected["storeMappingCandidates"], [])


if __name__ == "__main__":
    unittest.main()
