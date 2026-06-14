import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.ticket_sync_service import TicketSyncService


class TicketSyncMappingBoundaryTests(unittest.TestCase):
    """验证工单同步外部映射边界，避免远端拉取被外部字段规则二次解释。"""

    def test_remote_pull_detection_uses_internal_fields_without_external_mapping(self):
        """远端拉取应使用内部字段和日志提示，不应用外部映射配置。"""
        sync_object = SimpleNamespace(
            raw_payload={
                "ticketVender": "会命中错误映射的外部商家",
                "ticketModle": "会命中错误映射的外部模块",
                "ticketStatus": "外部状态",
                "ticketAssignee": "外部人员",
                "currentAssigneeEmail": "remote@example.com",
            },
            extra_data={
                "log_pull_hints": {
                    "vendorId": 1001,
                    "storeId": "S001",
                    "storeName": "远端门店",
                    "posNo": 9,
                    "modifyTime": "2026-06-14",
                }
            },
            project_code="",
            project_id=88,
            project_name="远端项目",
            merchant_name="远端项目",
            module_code="",
            module_name="远端模块",
            module_id=99,
            log_pull_config={},
            status="processing",
            current_assignee_id=66,
            current_assignee_name="内部处理人",
            version_key="v1.0.0",
            ticket_no="REMOTE-1",
            title="远端工单",
            description="远端描述",
            root_cause=None,
            solution=None,
        )

        with (
            patch.object(TicketSyncService, "_resolve_project_by_ticket_vender") as resolve_project,
            patch.object(TicketSyncService, "_resolve_module_by_ticket_modle") as resolve_module,
            patch.object(TicketSyncService, "_resolve_vendor_by_ticket_vender") as resolve_vendor,
            patch.object(TicketSyncService, "_resolve_status_by_external_value") as resolve_status,
            patch.object(TicketSyncService, "_resolve_assignee_by_external_value") as resolve_assignee,
            patch.object(
                TicketSyncService,
                "_resolve_remote_assignee_by_email_or_name",
                return_value=(None, "内部处理人"),
            ) as resolve_remote_assignee,
            patch.object(TicketSyncService, "_extract_pattern", return_value=None),
        ):
            detected = TicketSyncService._detect_fields(
                db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
                sync_object=sync_object,
                config={
                    "projectMappings": [{"keywords": ["错误"], "projectId": 1}],
                    "moduleMappings": [{"keywords": ["错误"], "moduleId": 2}],
                    "vendorMappings": [{"keywords": ["错误"], "vendorId": 3}],
                    "statusMappings": [{"keywords": ["外部状态"], "status": "closed"}],
                    "assigneeMappings": [{"keywords": ["外部人员"], "userId": 4}],
                    "posPatterns": [],
                    "scoPatterns": [],
                    "versionPatterns": [],
                },
                apply_external_mappings=False,
            )

        resolve_project.assert_not_called()
        resolve_module.assert_not_called()
        resolve_vendor.assert_not_called()
        resolve_status.assert_not_called()
        resolve_assignee.assert_not_called()
        resolve_remote_assignee.assert_called_once()
        self.assertEqual(resolve_remote_assignee.call_args.kwargs["assignee_email"], "remote@example.com")
        self.assertEqual(resolve_remote_assignee.call_args.kwargs["assignee_name"], "外部人员")
        self.assertIsNone(detected["projectId"])
        self.assertIsNone(detected["moduleId"])
        self.assertEqual(detected["vendorId"], 1001)
        self.assertEqual(detected["storeId"], "S001")
        self.assertEqual(detected["storeName"], "远端门店")
        self.assertEqual(detected["posNo"], 9)
        self.assertEqual(detected["status"], "processing")
        self.assertIsNone(detected["assigneeId"])
        self.assertEqual(detected["assigneeName"], "内部处理人")

    def test_external_detection_keeps_module_text_when_mapping_misses(self):
        """外部模块映射失败时应保留 ticketModle 文本，避免模块名称落库为空。"""
        sync_object = SimpleNamespace(
            raw_payload={"ticketModle": "外部模块文本"},
            extra_data={},
            project_code="",
            project_id=None,
            project_name="",
            merchant_name="",
            module_code="",
            module_name="",
            module_id=None,
            log_pull_config={},
            status="",
            current_assignee_id=None,
            current_assignee_name="",
            version_key="",
            ticket_no="EXT-3",
            title="外部工单",
            description="外部描述",
            root_cause=None,
            solution=None,
        )

        with patch.object(TicketSyncService, "_extract_pattern", return_value=None):
            detected = TicketSyncService._detect_fields(
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

        self.assertIsNone(detected["moduleId"])
        self.assertEqual(detected["moduleName"], "外部模块文本")

    def test_external_upsert_fills_empty_module_name_from_detected_text(self):
        """已有工单模块为空时，外部推送映射失败也应保留 ticketModle 文本。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="external", record_id="EXT-MODULE", record_url="", pushed_at=None),
            extra_data={},
            raw_payload={"ticketModle": "POS - 客户端"},
            ticket_no="EXT-MODULE",
            ticket_url=None,
            title="外部工单",
            description="外部描述",
            customer_priority="P3",
            internal_priority="P2",
            severity="",
            reporter_id=None,
            reporter_name="外部报告人",
            current_assignee_id=None,
            current_assignee_name="",
            first_line_assignee_id=None,
            first_line_assignee_name="",
            internal_owner_id=None,
            internal_owner_name="",
            status="processing",
            root_cause=None,
            solution=None,
            tags=None,
            project_id=None,
            project_name="",
            merchant_name="",
            module_id=999,
            module_name="",
            version_key="",
            log_pull_config={},
            create_time=None,
        )
        ticket = SimpleNamespace(
            extra_data={},
            customer_priority="P3",
            internal_priority="P2",
            severity="",
            reporter_id=1,
            reporter_name="tester",
            current_assignee_id=None,
            current_assignee_name="",
            first_line_assignee_id=None,
            first_line_assignee_name="",
            internal_owner_id=None,
            internal_owner_name="",
            status="pending",
            root_cause=None,
            solution=None,
            tags=None,
            ticket_url=None,
            project_id=None,
            merchant_name="",
            module_id=999,
            module_name="",
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncService._build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=ticket,
            sync_object=sync_object,
            detected={"moduleId": 999, "moduleName": "POS - 客户端"},
            current_user=current_user,
            sync_scene="external_sync",
        )

        self.assertNotIn("module_id", payload)
        self.assertEqual(payload["module_name"], "POS - 客户端")
        source_snapshot = payload["extra_data"][TicketSyncService.META_KEY]["source"]
        self.assertEqual(source_snapshot["moduleName"], "POS - 客户端")

    def test_external_detection_maps_three_person_roles(self):
        """外部推送应分别解析报告人、当前处理人和内部负责人。"""
        sync_object = SimpleNamespace(
            raw_payload={
                "reporterName": "外部一线",
                "currentAssigneeName": "外部当前处理人",
                "internalOwner": "外部内部负责人",
            },
            extra_data={
                "external_field_mapping": {
                    "reporterName": "外部一线",
                    "reporterEmail": "l1@example.com",
                    "currentAssigneeName": "外部当前处理人",
                    "currentAssigneeEmail": "assignee@example.com",
                    "internalOwner": "外部内部负责人",
                    "internalOwnerEmail": "owner@example.com",
                }
            },
            project_code="",
            project_id=None,
            project_name="",
            merchant_name="",
            module_code="",
            module_name="",
            module_id=None,
            log_pull_config={},
            status="",
            current_assignee_id=None,
            current_assignee_name="",
            first_line_assignee_id=None,
            first_line_assignee_name="",
            internal_owner_id=None,
            internal_owner_name="",
            version_key="",
            ticket_no="EXT-ROLE",
            title="外部工单",
            description="外部描述",
            root_cause=None,
            solution=None,
        )

        with (
            patch.object(TicketSyncService, "_extract_pattern", return_value=None),
            patch.object(
                TicketSyncService,
                "_resolve_external_person_by_mapping_or_email",
                side_effect=[
                    (22, "内部当前处理人"),
                    (11, "内部一线"),
                    (33, "内部负责人"),
                ],
            ) as resolve_person,
        ):
            detected = TicketSyncService._detect_fields(
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

        self.assertEqual(resolve_person.call_count, 3)
        self.assertEqual(detected["assigneeId"], 22)
        self.assertEqual(detected["assigneeName"], "内部当前处理人")
        self.assertEqual(detected["firstLineAssigneeId"], 11)
        self.assertEqual(detected["firstLineAssigneeName"], "内部一线")
        self.assertEqual(detected["internalOwnerId"], 33)
        self.assertEqual(detected["internalOwnerName"], "内部负责人")

    def test_remote_pull_upsert_does_not_fallback_to_remote_ids(self):
        """远端拉取落库时不使用远端项目、模块、人员ID，只保留可识别文本。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="public", record_id="REMOTE-2", record_url="", pushed_at=None),
            extra_data={},
            raw_payload={"currentAssigneeId": 66, "projectId": 88, "moduleId": 99},
            ticket_no="REMOTE-2",
            ticket_url=None,
            title="远端工单",
            description="远端描述",
            customer_priority="P3",
            internal_priority="P2",
            severity="",
            reporter_id=None,
            reporter_name="远端提单人",
            current_assignee_id=66,
            current_assignee_name="远端处理人",
            status="processing",
            root_cause=None,
            solution=None,
            tags=None,
            project_id=88,
            project_name="远端项目",
            merchant_name="远端项目",
            module_id=99,
            module_name="远端模块",
            version_key="",
            log_pull_config={},
            create_time=None,
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncService._build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=None,
            sync_object=sync_object,
            detected={"assigneeId": None, "assigneeName": "远端处理人"},
            current_user=current_user,
            sync_scene="remote_pull",
        )

        self.assertNotIn("project_id", payload)
        self.assertNotIn("module_id", payload)
        self.assertEqual(payload["merchant_name"], "远端项目")
        self.assertEqual(payload["module_name"], "远端模块")
        self.assertIsNone(payload["current_assignee_id"])
        self.assertEqual(payload["current_assignee_name"], "远端处理人")


class _EmptyQuery:
    """提供最小查询链，避免单元测试依赖真实数据库。"""

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


if __name__ == "__main__":
    unittest.main()
