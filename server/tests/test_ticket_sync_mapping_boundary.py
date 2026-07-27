import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_task.scheduler_maintenance import (
    _build_bitable_pull_config_override,
)
from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import TicketSyncAutomationModel
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ai.ticket_auto_classification_service import TicketAutoClassificationService
from modules.ticket.service.ai.ticket_light_ai_service import TicketLightAiService
from modules.ticket.service.collaboration.ticket_message_sync_service import TicketMessageSyncService
from modules.ticket.service.sync.ticket_batch_reclassification_service import TicketBatchReclassificationService
from modules.ticket.service.sync.ticket_bitable_pull_service import TicketBitablePullService
from modules.ticket.service.sync.ticket_external_bitable_email_service import TicketExternalBitableEmailService
from modules.ticket.service.sync.ticket_external_sync_request_service import TicketExternalSyncRequestService
from modules.ticket.service.sync.ticket_remote_sync_service import TicketRemoteSyncService
from modules.ticket.service.sync.ticket_sync_ai_config_service import TicketSyncAiConfigService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_comment_service import TicketSyncCommentService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_delivery_service import TicketSyncDeliveryService
from modules.ticket.service.sync.ticket_sync_field_mapping_service import TicketSyncFieldMappingService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.sync.ticket_sync_notify_service import TicketSyncNotifyService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService
from modules.ticket.service.sync.ticket_sync_post_process_service import TicketSyncPostProcessService
from modules.ticket.service.sync.ticket_sync_service import TicketSyncService
from modules.ticket.util.ticket_feishu_bitable_util import FeishuBitableUtil


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
            patch.object(TicketSyncFieldMappingService, "resolve_project_by_ticket_vender") as resolve_project,
            patch.object(TicketSyncFieldMappingService, "resolve_module_by_ticket_modle") as resolve_module,
            patch.object(TicketSyncFieldMappingService, "resolve_vendor_by_ticket_vender") as resolve_vendor,
            patch.object(TicketSyncFieldMappingService, "resolve_assignee_by_external_value") as resolve_assignee,
            patch.object(
                TicketSyncFieldMappingService,
                "resolve_external_person_by_mapping_or_email",
                side_effect=[(None, "内部处理人"), (None, ""), (None, "")],
            ) as resolve_person,
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
        ):
            detected = TicketSyncAutomationService.detect_fields(
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
        resolve_assignee.assert_not_called()
        self.assertEqual(resolve_person.call_count, 3)
        self.assertEqual(resolve_person.call_args_list[0].kwargs["person_email"], "remote@example.com")
        self.assertEqual(resolve_person.call_args_list[0].kwargs["person_text"], "外部人员")
        self.assertIsNone(detected["projectId"])
        self.assertIsNone(detected["moduleId"])
        self.assertEqual(detected["vendorId"], 1001)
        self.assertEqual(detected["storeId"], "S001")
        self.assertEqual(detected["storeName"], "远端门店")
        self.assertEqual(detected["posNo"], 9)
        self.assertEqual(detected["status"], "closed")
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

        with patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None):
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

        self.assertIsNone(detected["moduleId"])
        self.assertEqual(detected["moduleName"], "外部模块文本")

    def test_external_detection_keeps_project_text_when_mapping_misses(self):
        """外部项目映射失败时应保留 ticketVender 文本，避免项目名称落库为空。"""
        sync_object = SimpleNamespace(
            raw_payload={"ticketVender": "外部项目文本"},
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
            ticket_no="EXT-PROJECT",
            title="外部工单",
            description="外部描述",
            root_cause=None,
            solution=None,
        )

        with (
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
            patch.object(TicketSyncFieldMappingService, "resolve_project_by_ticket_vender", return_value=(None, "")),
        ):
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

        self.assertIsNone(detected["projectId"])
        self.assertEqual(detected["projectName"], "外部项目文本")

    def test_external_detection_uses_project_and_module_code_after_mapping_miss(self):
        """外部推送在 ticketVender/ticketModle 映射未命中后，应按拆分前逻辑使用业务码兜底。"""
        project = SimpleNamespace(project_id=101, project_name="支付平台", project_code="pay")
        module = SimpleNamespace(module_id=201, module_name="支付模块", module_code="pos")
        sync_object = SimpleNamespace(
            raw_payload={"ticketVender": "外部项目文本", "ticketModle": "外部模块文本"},
            extra_data={},
            project_code="pay",
            project_id=None,
            project_name="",
            merchant_name="",
            module_code="pos",
            module_name="",
            module_id=None,
            log_pull_config={},
            status="",
            current_assignee_id=None,
            current_assignee_name="",
            version_key="",
            ticket_no="EXT-CODE",
            title="外部工单",
            description="外部描述",
            root_cause=None,
            solution=None,
        )

        with (
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
            patch.object(TicketSyncFieldMappingService, "resolve_project_by_ticket_vender", return_value=(None, "")),
            patch.object(TicketSyncFieldMappingService, "resolve_module_by_ticket_modle", return_value=None),
            patch.object(TicketSyncFieldMappingService, "resolve_vendor_by_project", return_value=None),
        ):
            detected = TicketSyncAutomationService.detect_fields(
                db=_ModelQueryDb(project=project, module=module),
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

        self.assertEqual(detected["projectId"], 101)
        self.assertEqual(detected["projectName"], "支付平台")
        self.assertEqual(detected["moduleId"], 201)
        self.assertEqual(detected["moduleName"], "支付模块")

    def test_remote_pull_detection_uses_project_and_module_code(self):
        """内网拉取外部数据时也应通过 projectCode/moduleCode 绑定本地项目模块。"""
        project = SimpleNamespace(project_id=101, project_name="支付平台", project_code="pay")
        module = SimpleNamespace(module_id=201, module_name="支付模块", module_code="pos")
        sync_object = SimpleNamespace(
            raw_payload={},
            extra_data={},
            project_code="pay",
            project_id=None,
            project_name="远端项目文本",
            merchant_name="远端项目文本",
            module_code="pos",
            module_name="远端模块文本",
            module_id=None,
            log_pull_config={},
            status="processing",
            current_assignee_id=None,
            current_assignee_name="",
            version_key="",
            ticket_no="REMOTE-CODE",
            title="远端工单",
            description="远端描述",
            root_cause=None,
            solution=None,
        )

        with (
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
            patch.object(
                TicketSyncFieldMappingService,
                "resolve_external_person_by_mapping_or_email",
                side_effect=[(None, ""), (None, ""), (None, "")],
            ),
        ):
            detected = TicketSyncAutomationService.detect_fields(
                db=_ModelQueryDb(project=project, module=module),
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
                apply_external_mappings=False,
            )

        self.assertEqual(detected["projectId"], 101)
        self.assertEqual(detected["projectName"], "支付平台")
        self.assertEqual(detected["moduleId"], 201)
        self.assertEqual(detected["moduleName"], "支付模块")

    def test_external_upsert_fills_project_name_from_detected_text(self):
        """已有工单项目为空时，外部推送映射失败也应保留 ticketVender 文本。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="external", record_id="EXT-PROJECT", record_url="", pushed_at=None),
            extra_data={},
            raw_payload={"ticketVender": "外部项目文本"},
            ticket_no="EXT-PROJECT",
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
            project_id=888,
            project_name="",
            merchant_name="",
            module_id=None,
            module_name="",
            version_key="",
            log_pull_config={},
            create_time=None,
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=None,
            sync_object=sync_object,
            detected={"projectId": 888, "projectName": "外部项目文本"},
            current_user=current_user,
            sync_scene="external_sync",
        )

        self.assertIsNone(payload["project_id"])
        self.assertEqual(payload["merchant_name"], "外部项目文本")

    def test_manual_update_keeps_existing_version_when_request_has_no_version(self):
        """手动编辑请求没有版本号时，不应清空工单已有版本号。"""
        ticket = SimpleNamespace(extra_data={"version_key": "1.2.3"})
        form_extra_data = {"version_key": ""}
        extra_data = dict(ticket.extra_data or {})
        for version_field in ("version_key", "versionKey", "version", "deployVersion", "deploy_version", "appVersion"):
            if version_field in form_extra_data and not str(form_extra_data.get(version_field) or "").strip():
                form_extra_data.pop(version_field, None)
        extra_data.update(form_extra_data)

        self.assertEqual(extra_data["version_key"], "1.2.3")

    def test_ai_analysis_extracts_version_from_log_when_request_missing(self):
        """AI分析未传版本号时，应从日志记录提取版本号并返回该日志记录。"""
        ticket = SimpleNamespace(ticket_id=1001, extra_data={})
        log_record = SimpleNamespace(id=2001)

        with (
            patch.object(TicketAiAnalysisService, "_resolve_log_pull_record", return_value=log_record),
            patch.object(TicketAiAnalysisService, "_resolve_version_key", return_value=""),
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
            patch(
                "modules.ticket.service.ai.ticket_ai_analysis_service."
                "TicketLogPullService._ensure_ticket_version_key_from_log",
                return_value="2.0.1",
            ),
            patch(
                "modules.ticket.service.ai.ticket_ai_analysis_service."
                "TicketLogPullDao.get_latest_success_record_by_ticket_id",
                return_value=None,
            ),
            patch(
                "modules.ticket.service.ai.ticket_ai_analysis_service.TicketDao.get_ticket_by_id",
                return_value=SimpleNamespace(extra_data={"version_key": "2.0.1"}),
            ),
        ):
            version_key, selected_record = TicketAiAnalysisService._ensure_version_key_for_analysis(
                SimpleNamespace(),
                ticket,
                SimpleNamespace(log_pull_record_id=None),
            )

        self.assertEqual(version_key, "2.0.1")
        self.assertEqual(selected_record, log_record)

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
            issue_type_id="",
            issue_type_name="",
            is_problem=None,
            root_cause_type="",
            solution_type="",
            resolution_code="",
            resolution_name="",
            problem_pattern_code="",
            problem_pattern_name="",
            problem_pattern_confidence=None,
            problem_pattern_source="",
            problem_pattern_verified=None,
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

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=ticket,
            sync_object=sync_object,
            detected={"moduleId": 999, "moduleName": "POS - 客户端"},
            current_user=current_user,
            sync_scene="external_sync",
        )

        self.assertIsNone(payload["module_id"])
        self.assertEqual(payload["module_name"], "POS - 客户端")
        source_snapshot = payload["extra_data"][TicketSyncPayloadService.META_KEY]["source"]
        self.assertEqual(source_snapshot["moduleName"], "POS - 客户端")

    def test_external_upsert_overwrites_old_project_module_when_mapping_misses(self):
        """已有工单再次同步时，外部项目/模块变化应覆盖旧ID并保留本次外部文本。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="external", record_id="EXT-CHANGE", record_url="", pushed_at=None),
            extra_data={},
            raw_payload={"ticketVender": "新外部项目", "ticketModle": "新外部模块"},
            ticket_no="EXT-CHANGE",
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
            project_code="",
            project_name="",
            merchant_name="",
            module_id=None,
            module_code="",
            module_name="",
            version_key="",
            log_pull_config={},
            create_time=None,
        )
        ticket = SimpleNamespace(
            extra_data={"log_pull_hints": {"vendorId": 1001, "storeId": "S001"}},
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
            issue_type_id="",
            issue_type_name="",
            is_problem=None,
            root_cause_type="",
            solution_type="",
            resolution_code="",
            resolution_name="",
            problem_pattern_code="",
            problem_pattern_name="",
            problem_pattern_confidence=None,
            problem_pattern_source="",
            problem_pattern_verified=None,
            root_cause=None,
            solution=None,
            tags=None,
            ticket_url=None,
            project_id=10,
            merchant_name="旧内部项目",
            module_id=20,
            module_name="旧内部模块",
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=ticket,
            sync_object=sync_object,
            detected={"projectId": None, "projectName": "新外部项目", "moduleId": None, "moduleName": "新外部模块"},
            current_user=current_user,
            sync_scene="external_sync",
        )

        self.assertIsNone(payload["project_id"])
        self.assertEqual(payload["merchant_name"], "新外部项目")
        self.assertIsNone(payload["module_id"])
        self.assertEqual(payload["module_name"], "新外部模块")
        self.assertNotIn("vendorId", payload["extra_data"].get("log_pull_hints", {}))

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
            patch.object(TicketSyncAutomationService, "extract_pattern", return_value=None),
            patch.object(
                TicketSyncFieldMappingService,
                "resolve_external_person_by_mapping_or_email",
                side_effect=[
                    (22, "内部当前处理人"),
                    (11, "内部一线"),
                    (33, "内部负责人"),
                ],
            ) as resolve_person,
        ):
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

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=None,
            sync_object=sync_object,
            detected={"assigneeId": None, "assigneeName": "远端处理人"},
            current_user=current_user,
            sync_scene="remote_pull",
        )

        self.assertIsNone(payload["project_id"])
        self.assertIsNone(payload["module_id"])
        self.assertEqual(payload["merchant_name"], "远端项目")
        self.assertEqual(payload["module_name"], "远端模块")
        self.assertIsNone(payload["current_assignee_id"])
        self.assertEqual(payload["current_assignee_name"], "远端处理人")

    def test_remote_pull_upsert_overwrites_old_project_module_text(self):
        """远端拉取更新已有工单时，应清空远端ID并同步远端最新项目/模块文本。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="public", record_id="REMOTE-CHANGE", record_url="", pushed_at=None),
            extra_data={},
            raw_payload={"projectId": 88, "moduleId": 99},
            ticket_no="REMOTE-CHANGE",
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
            first_line_assignee_id=None,
            first_line_assignee_name="",
            internal_owner_id=None,
            internal_owner_name="",
            status="processing",
            root_cause=None,
            solution=None,
            tags=None,
            project_id=88,
            project_code="",
            project_name="新远端项目",
            merchant_name="新远端项目",
            module_id=99,
            module_code="",
            module_name="新远端模块",
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
            issue_type_id="",
            issue_type_name="",
            is_problem=None,
            root_cause_type="",
            solution_type="",
            resolution_code="",
            resolution_name="",
            problem_pattern_code="",
            problem_pattern_name="",
            problem_pattern_confidence=None,
            problem_pattern_source="",
            problem_pattern_verified=None,
            root_cause=None,
            solution=None,
            tags=None,
            ticket_url=None,
            project_id=10,
            merchant_name="旧内网项目",
            module_id=20,
            module_name="旧内网模块",
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, _meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=ticket,
            sync_object=sync_object,
            detected={"assigneeId": None, "assigneeName": "远端处理人"},
            current_user=current_user,
            sync_scene="remote_pull",
        )

        self.assertIsNone(payload["project_id"])
        self.assertEqual(payload["merchant_name"], "新远端项目")
        self.assertIsNone(payload["module_id"])
        self.assertEqual(payload["module_name"], "新远端模块")

    def test_remote_sync_service_builds_upsert_model_with_alias_fields(self):
        """远端拉取服务应保留拆分前字段别名兼容，不回退调用 TicketSyncService 私有方法。"""
        sync_object = TicketRemoteSyncService.build_upsert_model(
            {
                "ticketId": 1001,
                "ticketNo": "REMOTE-ALIAS",
                "title": "远端工单",
                "description": "远端描述",
                "module_name": "远端模块",
                "project_name": "远端项目",
                "internalPriority": "P4",
                "syncSummary": {"revision": 7, "ticketUrl": "https://example.com/ticket/1001"},
                "extraData": {
                    "external_field_mapping": {
                        "ticketStatus": "processing",
                        "internalOwnerEmail": "owner@example.com",
                    },
                    "log_pull_hints": {"storeId": "S001", "posNo": "9"},
                },
                "step_reason": "20260704：排查过程",
            },
            remote_sync={"consumer": "inner", "sourceSystem": "public"},
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.ticket_no, "REMOTE-ALIAS")
        self.assertEqual(sync_object.module_name, "远端模块")
        self.assertEqual(sync_object.project_name, "远端项目")
        self.assertEqual(sync_object.source.record_id, "1001")
        self.assertEqual(sync_object.source.record_url, "https://example.com/ticket/1001")
        self.assertEqual(sync_object.sync_consumer, "inner")
        self.assertEqual(sync_object.status, "processing")
        self.assertEqual(sync_object.customer_priority, "Level D")
        self.assertEqual(sync_object.internal_priority, "P4")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["customerPriority"], "Level D")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["internalPriority"], "P4")
        self.assertEqual(
            sync_object.extra_data["external_field_mapping"]["internalOwnerEmail"],
            "owner@example.com",
        )
        self.assertEqual(sync_object.extra_data["_remote_sync_revision"], 7)
        self.assertEqual(sync_object.log_pull_config["storeId"], "S001")
        self.assertEqual(sync_object.step_reason, "20260704：排查过程")

    def test_remote_sync_service_skips_local_newer_revision(self):
        """远端 revision 不大于本地 sourceRevision 时，应跳过覆盖并返回明确原因。"""
        local_ticket = SimpleNamespace(extra_data={TicketSyncPayloadService.META_KEY: {"sourceRevision": 8}})

        should_apply, reason = TicketRemoteSyncService.should_apply_remote_sync_item(
            local_ticket=local_ticket,
            remote_sync_revision=7,
            remote_pushed_at="2026-07-04T10:00:00",
        )

        self.assertFalse(should_apply)
        self.assertEqual(reason, "remote_revision_not_newer(remote=7, local=8)")

    def test_bitable_email_enrich_skips_when_record_already_success(self):
        """同一 recordId 已成功补齐过邮箱时，不应再次请求多维表格。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(record_id="rec_001"),
            ticket_no="EXT-BITABLE",
            extra_data={},
        )
        existing_ticket = SimpleNamespace(
            extra_data={
                TicketSyncPayloadService.META_KEY: {
                    "bitableEmailSync": {
                        "status": "success",
                        "recordId": "rec_001",
                    }
                }
            }
        )

        with patch.object(TicketExternalBitableEmailService, "query_record_fields") as query_fields:
            result = TicketExternalBitableEmailService.enrich_person_emails(
                {"externalSyncBitable": {"enabled": True}},
                sync_object,
                existing_ticket,
            )

        query_fields.assert_not_called()
        self.assertIs(result, sync_object)

    def test_bitable_email_success_meta_is_attached_to_upsert_payload(self):
        """多维表格邮箱补齐成功后，应把成功状态写入 external_sync 元数据。"""
        sync_object = SimpleNamespace(
            source=SimpleNamespace(system="external", record_id="rec_002", record_url="", pushed_at=None),
            extra_data={
                "_bitable_email_sync": {
                    "status": "success",
                    "recordId": "rec_002",
                    "emailKeys": ["reporterEmail"],
                    "syncedAt": "2026-06-16T10:00:00",
                },
                "external_field_mapping": {
                    "reporterEmail": "l1@example.com",
                    "bitableRecordId": "rec_002",
                },
            },
            raw_payload={},
            ticket_no="EXT-BITABLE-2",
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
            module_id=None,
            module_name="",
            version_key="",
            log_pull_config={},
            create_time=None,
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name=""))

        payload, meta, _revision = TicketSyncPayloadService.build_upsert_payload(
            db=SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery()),
            ticket=None,
            sync_object=sync_object,
            detected={},
            current_user=current_user,
            sync_scene="external_sync",
        )

        self.assertEqual(meta["bitableEmailSync"]["status"], "success")
        self.assertEqual(meta["bitableEmailSync"]["recordId"], "rec_002")
        self.assertNotIn("_bitable_email_sync", payload["extra_data"])
        self.assertEqual(
            payload["extra_data"][TicketSyncPayloadService.META_KEY]["bitableEmailSync"]["recordId"],
            "rec_002",
        )

    def test_person_reminder_uses_search_record_url_when_local_ticket_url_missing(self):
        """本地工单没有详情 URL 时，催办明细应优先使用飞书搜索结果返回的记录 URL。"""
        db = SimpleNamespace(query=lambda *_args, **_kwargs: _EmptyQuery())
        config = {
            "dataSource": "bitable",
            "appToken": "base_token",
            "tableId": "tbl_token",
            "viewId": "vew_token",
            "personField": "处理人",
            "timeField": "更新时间",
            "thresholdMinutes": 1,
        }
        record = {
            "record_id": "rec_003",
            "record_url": "https://duodian.feishu.cn/record/RotorqQTyeb46qc3BzPcrcvSnSh",
            "fields": {
                "处理人": [{"email": "owner@example.com", "name": "负责人"}],
                "更新时间": "2020-01-01 09:00:00",
                "ticketNo": "EXT-003",
                "title": "待处理工单",
            },
        }

        with patch.object(TicketSyncNotifyService, "query_bitable_records", return_value=[record]):
            result = TicketSyncNotifyService._collect_person_overdue_data(
                db,
                config=config,
                email="owner@example.com",
                all=True,
            )

        rows = result["people"][0]["rows"]
        self.assertEqual(
            rows[0]["detailUrl"],
            "https://duodian.feishu.cn/record/RotorqQTyeb46qc3BzPcrcvSnSh",
        )

    def test_sync_config_keeps_bitable_common_independent_from_scene_sections(self):
        """保存态配置不应把多维表格公共配置写入各独立业务配置段。"""
        config = TicketSyncConfigService.normalize_sync_config(
            {
                "feishuAuth": {"appId": "app_a", "appSecret": "secret_a"},
                "bitableCommon": {
                    "appToken": "common_token",
                    "tableId": "common_table",
                    "viewId": "common_view",
                    "pageSize": 123,
                    "filterFormula": "CurrentValue.[状态] != \"已关闭\"",
                },
                "personReminder": {"enabled": True, "personField": "处理人", "timeField": "更新时间"},
                "summaryReport": {"enabled": True, "dataSource": "bitable"},
                "externalSyncBitable": {"enabled": True},
                "bitablePull": {"enabled": True},
            }
        )

        self.assertEqual(config["personReminder"]["appToken"], "")
        self.assertEqual(config["personReminder"]["tableId"], "")
        self.assertEqual(config["personReminder"]["viewId"], "")
        self.assertEqual(config["personReminder"]["pageSize"], 500)
        self.assertEqual(config["summaryReport"]["appToken"], "")
        self.assertEqual(config["summaryReport"]["filterFormula"], "")
        self.assertEqual(config["externalSyncBitable"]["appToken"], "")
        self.assertEqual(config["externalSyncBitable"]["appId"], "")
        self.assertEqual(config["externalSyncBitable"]["appSecret"], "")
        self.assertEqual(config["bitablePull"]["appToken"], "")
        self.assertEqual(config["bitablePull"]["tableId"], "")
        self.assertEqual(config["bitablePull"]["viewId"], "")
        self.assertEqual(config["bitablePull"]["filterFormula"], "")

    def test_sync_config_normalizes_light_ai_sections_without_legacy_fields(self):
        """五类轻量 AI 配置应统一归一化到工单同步配置，并清理旧内联字段。"""
        config = TicketSyncConfigService.normalize_sync_config(
            {
                "translateConfig": {"enabled": True, "providerCode": " provider_a "},
                "titleSummaryConfig": {"enabled": True, "providerCode": "provider_b"},
                "knowledgeConfig": {"enabled": True, "providerCode": "provider_c"},
                "aiClassification": {"enabled": True, "promptContent": "旧内联提示词"},
                "bitablePull": {"automation": {"autoTranslate": True}},
            }
        )

        self.assertEqual(config["translateConfig"]["providerCode"], "provider_a")
        self.assertEqual(config["translateConfig"]["promptCode"], "ticket_translate_default")
        self.assertEqual(config["titleSummaryConfig"]["promptCode"], "ticket_title_summary_default")
        self.assertEqual(config["knowledgeConfig"]["promptCode"], "ticket_knowledge_extract_default")
        self.assertEqual(config["aiClassification"]["promptCode"], "ticket_stat_classify_default")
        self.assertNotIn("promptContent", config["aiClassification"])
        self.assertNotIn("automation", config["bitablePull"])

    def test_light_ai_settings_only_read_ticket_sync_config(self):
        """轻量 AI 任务设置应只读取 ticket.sync.automation，不再读取旧 ticket.ai 标量键。"""
        row = SimpleNamespace(
            config_value=(
                '{"translateConfig":{"enabled":true,"providerCode":"provider_new",'
                '"promptCode":"ticket_translate_default"}}'
            )
        )
        db = SimpleNamespace(query=lambda *_args, **_kwargs: _SingleRowQuery(row))

        section = TicketSyncAiConfigService.load_section(db, "translateConfig")

        self.assertTrue(section["enabled"])
        self.assertEqual(section["providerCode"], "provider_new")

    def test_group_push_condition_uses_workflow_status_display_name(self):
        """群推送条件应通过 status_name 匹配工作流状态显示名，同时保留 status 编码。"""
        ticket = Ticket(
            ticket_id=1,
            ticket_no="T-STATUS-NAME",
            title="状态条件测试",
            description="状态条件测试",
            status="processing_two",
        )
        with patch.object(
            TicketDao,
            "get_workflow_status_by_code",
            return_value=SimpleNamespace(name="2. 1.5线处理"),
        ):
            skipped, reason = TicketSyncGroupPushService.should_skip_auto_group_push_by_condition(
                db=SimpleNamespace(),
                ticket=ticket,
                group_config={
                    "autoPushCondition": (
                        "status == 'processing_two' and status_name == '2. 1.5线处理'"
                    )
                },
            )

        self.assertFalse(skipped)
        self.assertIsNone(reason)

    def test_bitable_runtime_config_inherits_common_without_polluting_saved_config(self):
        """运行时多维表格配置应独立配置优先，独立为空时才继承公共配置。"""
        config = TicketSyncConfigService.normalize_sync_config(
            {
                "feishuAuth": {"appId": "app_a", "appSecret": "secret_a"},
                "bitableCommon": {
                    "appToken": "common_token",
                    "tableId": "common_table",
                    "viewId": "common_view",
                    "pageSize": 123,
                    "filterFormula": "CurrentValue.[状态] != \"已关闭\"",
                },
                "bitablePull": {
                    "enabled": True,
                    "appToken": "pull_token",
                    "fieldMappings": [{"sourceField": "工单号", "targetField": "ticketNo"}],
                },
            }
        )

        runtime_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "bitablePull",
            TicketSyncConfigService.default_bitable_pull_config(),
        )

        self.assertEqual(runtime_config["appId"], "app_a")
        self.assertEqual(runtime_config["appSecret"], "secret_a")
        self.assertEqual(runtime_config["appToken"], "pull_token")
        self.assertEqual(runtime_config["tableId"], "common_table")
        self.assertEqual(runtime_config["viewId"], "common_view")
        self.assertEqual(runtime_config["filterFormula"], "CurrentValue.[状态] != \"已关闭\"")

    def test_bitable_pull_record_skips_when_snapshot_not_changed(self):
        """主动拉取记录快照未变化时应跳过，避免每次任务都递增 revision。"""
        sync_object = SimpleNamespace(
            extra_data={"bitable_pull": {"recordId": "rec_001", "snapshotHash": "hash_001"}},
        )
        existing_ticket = SimpleNamespace(
            extra_data={"bitable_pull": {"recordId": "rec_001", "snapshotHash": "hash_001"}}
        )

        should_skip, reason = TicketBitablePullService.should_skip_bitable_pull_record(
            existing_ticket=existing_ticket,
            sync_object=sync_object,
        )

        self.assertTrue(should_skip)
        self.assertEqual(reason, "snapshot_not_changed")

    def test_bitable_pull_builds_sync_object_from_field_mappings(self):
        """主动拉取应按字段映射生成外部同步模型，并携带字段映射快照。"""
        record = {
            "record_id": "rec_100",
            "record_url": "https://duodian.feishu.cn/record/RotorqQTyeb46qc3BzPcrcvSnSh",
            "created_time": "2026-06-21 10:00:00",
            "fields": {
                "工单号": "T-100",
                "标题": "支付失败",
                "描述": "顾客支付时报错",
                "优先级": "P1",
                "商家": "示例商家",
                "模块": "支付模块",
                "提单人": "张三",
                "创建时间": "2026-06-21 09:59:00",
            },
        }
        config = {
            "appToken": "app_token",
            "tableId": "tbl_100",
            "viewId": "vew_100",
            "sourceSystem": "feishu_bitable_pull",
            "includeRecordUrl": True,
            "updatedAtField": "创建时间",
        }
        field_mappings = [
            {"sourceField": "工单号", "targetField": "ticketNo"},
            {"sourceField": "标题", "targetField": "title"},
            {"sourceField": "描述", "targetField": "description"},
            {"sourceField": "优先级", "targetField": "internalPriority"},
            {"sourceField": "商家", "targetField": "ticketVender"},
            {"sourceField": "模块", "targetField": "ticketModle"},
            {"sourceField": "提单人", "targetField": "reporterName"},
            {"sourceField": "创建时间", "targetField": "createTime"},
        ]

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config=config,
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.ticket_no, "T-100")
        self.assertEqual(sync_object.title, "支付失败")
        self.assertEqual(sync_object.source.record_id, "rec_100")
        self.assertEqual(
            sync_object.ticket_url,
            "https://duodian.feishu.cn/record/RotorqQTyeb46qc3BzPcrcvSnSh",
        )
        self.assertEqual(
            sync_object.extra_data["bitable_pull"]["fieldMappings"]["ticketNo"],
            "工单号",
        )
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["ticketVender"], "示例商家")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["ticketModle"], "支付模块")
        self.assertEqual(sync_object.project_name, "示例商家")
        self.assertEqual(sync_object.module_name, "支付模块")

    def test_bitable_pull_preserves_rich_text_newline_segments(self):
        """主动拉取富文本字段应保留真实换行，避免描述和评论内容挤在一起。"""
        record = {
            "record_id": "rec_rich_text",
            "fields": {
                "工单号": "T-RICH",
                "描述": [
                    {"text": "第一行", "type": "text"},
                    {"text": "\n", "type": "text"},
                    {"text": "", "type": "text"},
                    {"text": "第二行", "type": "text"},
                ],
                "排查过程": [
                    {"text": "20260624 张三：已确认门店网络正常", "type": "text"},
                    {"text": "\n", "type": "text"},
                    {"text": "20260625 李四：等待研发排查", "type": "text"},
                    {"text": "王五", "type": "mention", "mention_user_id": "ou_wangwu"},
                    {"text": "支付链路", "type": "text"},
                ],
                "优先级": "P1",
                "商家": "示例商家",
                "模块": "支付模块",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "排查过程", "targetField": "stepReason"},
                {"sourceField": "优先级", "targetField": "internalPriority"},
                {"sourceField": "商家", "targetField": "ticketVender"},
                {"sourceField": "模块", "targetField": "ticketModle"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.description, "第一行\n第二行")
        self.assertEqual(
            sync_object.extra_data["external_field_mapping"]["stepReason"],
            "20260624 张三：已确认门店网络正常\n20260625 李四：等待研发排查@王五支付链路",
        )
        self.assertEqual(
            sync_object.extra_data["_bitable_field_segments"]["stepReason"][3]["openId"],
            "ou_wangwu",
        )
        segments = TicketSyncCommentService.parse_step_reason_segments(
            sync_object.extra_data["external_field_mapping"]["stepReason"]
        )
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["personName"], "张三")
        self.assertEqual(segments[1]["personName"], "李四")
        with (
            patch(
                "modules.ticket.service.sync.ticket_sync_comment_service."
                "TicketCommentCoreService.upsert_synced_comment"
            ) as upsert,
        ):
            upsert.return_value = (SimpleNamespace(id=1), "created")
            TicketSyncCommentService.sync_step_reason_comments(
                SimpleNamespace(),
                ticket=SimpleNamespace(ticket_id=1),
                sync_object=sync_object,
            )
        self.assertEqual(
            upsert.call_args_list[1].kwargs["attachments"]["content_segments"][1]["openId"],
            "ou_wangwu",
        )

    def test_bitable_pull_accepts_module_name_target_alias(self):
        """主动拉取目标字段使用 moduleName 时，应归一为 ticketModle 满足必填校验。"""
        record = {
            "record_id": "rec_101",
            "fields": {
                "工单号": "T-101",
                "描述": "顾客支付时报错",
                "优先级": "P1",
                "商家": "示例商家",
                "模块": "支付模块",
                "提单人": "张三",
                "创建时间": "2026-06-21 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "优先级", "targetField": "internalPriority"},
                {"sourceField": "商家", "targetField": "ticketVender"},
                {"sourceField": "模块", "targetField": "moduleName"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.ticket_no, "T-101")
        self.assertEqual(
            sync_object.extra_data["bitable_pull"]["fieldMappings"]["ticketModle"],
            "模块",
        )

    def test_bitable_pull_preserves_project_module_owner_mapping_for_detection(self):
        """主动拉取映射出的项目、模块和内部负责人应保留给入库识别阶段使用。"""
        record = {
            "record_id": "rec_102",
            "fields": {
                "工单号": "T-102",
                "描述": "Checkout failed",
                "优先级": "P2",
                "项目": "海外收银",
                "模块": "POS - 支付",
                "内部负责人": "李四",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "优先级", "targetField": "internalPriority"},
                {"sourceField": "项目", "targetField": "projectName"},
                {"sourceField": "模块", "targetField": "moduleName"},
                {"sourceField": "内部负责人", "targetField": "internalOwnerName"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.project_name, "海外收银")
        self.assertEqual(sync_object.module_name, "POS - 支付")
        self.assertEqual(sync_object.internal_owner_name, "李四")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["ticketVender"], "海外收银")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["ticketModle"], "POS - 支付")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["internalOwner"], "李四")

    def test_bitable_pull_uses_customer_priority_when_internal_priority_missing(self):
        """主动拉取内部优先级为空时，应使用对方优先级兜底，避免优先级反写或缺失。"""
        record = {
            "record_id": "rec_priority",
            "fields": {
                "工单号": "T-PRIORITY",
                "描述": "Checkout failed",
                "对方优先级": "Level A",
                "内部优先级": "",
                "项目": "海外收银",
                "模块": "POS - 支付",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "对方优先级", "targetField": "customerPriority"},
                {"sourceField": "内部优先级", "targetField": "internalPriority"},
                {"sourceField": "项目", "targetField": "projectName"},
                {"sourceField": "模块", "targetField": "moduleName"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.customer_priority, "Level A")
        self.assertEqual(sync_object.internal_priority, "P1")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["customerPriority"], "Level A")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["internalPriority"], "P1")

    def test_bitable_pull_uses_internal_priority_when_customer_priority_missing(self):
        """主动拉取对方优先级为空时，应使用内部优先级转换外部优先级。"""
        record = {
            "record_id": "rec_priority_reverse",
            "fields": {
                "工单号": "T-PRIORITY-REVERSE",
                "描述": "Checkout failed",
                "对方优先级": "",
                "内部优先级": "P2",
                "项目": "海外收银",
                "模块": "POS - 支付",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "对方优先级", "targetField": "customerPriority"},
                {"sourceField": "内部优先级", "targetField": "internalPriority"},
                {"sourceField": "项目", "targetField": "projectName"},
                {"sourceField": "模块", "targetField": "moduleName"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.customer_priority, "Level B")
        self.assertEqual(sync_object.internal_priority, "P2")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["customerPriority"], "Level B")
        self.assertEqual(sync_object.extra_data["external_field_mapping"]["internalPriority"], "P2")

    def test_bitable_pull_preserves_current_assignee_and_internal_owner_aliases(self):
        """主动拉取当前处理人和内部负责人别名应进入顶层模型和外部字段快照。"""
        record = {
            "record_id": "rec_person",
            "fields": {
                "工单号": "T-PERSON",
                "描述": "Checkout failed",
                "内部优先级": "P2",
                "项目": "海外收银",
                "模块": "POS - 支付",
                "提单人": "张三",
                "当前负责人": "李四",
                "当前负责人邮箱": "lisi@example.com",
                "内部负责人": "王五",
                "内部负责人邮箱": "wangwu@example.com",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        field_mappings = TicketSyncConfigService.normalize_bitable_field_mappings(
            [
                {"sourceField": "工单号", "targetField": "ticketNo"},
                {"sourceField": "描述", "targetField": "description"},
                {"sourceField": "内部优先级", "targetField": "internalPriority"},
                {"sourceField": "项目", "targetField": "projectName"},
                {"sourceField": "模块", "targetField": "moduleName"},
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "当前负责人", "targetField": "ticketAssigneeName"},
                {"sourceField": "当前负责人邮箱", "targetField": "ticketAssigneeEmail"},
                {"sourceField": "内部负责人", "targetField": "internalOwnerName"},
                {"sourceField": "内部负责人邮箱", "targetField": "internalOwnerEmail"},
                {"sourceField": "创建时间", "targetField": "createTime"},
            ]
        )

        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record=record,
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=field_mappings,
        )

        self.assertIsNotNone(sync_object)
        self.assertEqual(sync_object.current_assignee_name, "李四")
        self.assertEqual(sync_object.internal_owner_name, "王五")
        external_mapping = sync_object.extra_data["external_field_mapping"]
        self.assertEqual(external_mapping["ticketAssignee"], "李四")
        self.assertEqual(external_mapping["currentAssigneeName"], "李四")
        self.assertEqual(external_mapping["ticketAssigneeEmail"], "lisi@example.com")
        self.assertEqual(external_mapping["currentAssigneeEmail"], "lisi@example.com")
        self.assertEqual(external_mapping["internalOwner"], "王五")
        self.assertEqual(external_mapping["internalOwnerEmail"], "wangwu@example.com")

    def test_bitable_record_url_returns_empty_when_only_record_id_exists(self):
        """仅有 record_id 且没有飞书返回的详情 URL 时，不应伪造不可访问链接。"""
        record_url = TicketSyncNotifyService.get_bitable_record_url(
            {"appToken": "base_token", "tableId": "tbl_token", "viewId": "vew_token"},
            "rec_404",
        )

        self.assertEqual(record_url, "")

    def test_preview_bitable_pull_fields_uses_field_metadata_without_filters(self):
        """字段预览应读取字段元数据，且不受主动拉取过滤条件和时间窗口影响。"""
        config = TicketSyncConfigService.default_sync_config()
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "viewId": "view_id",
                "filterFormula": {
                    "conjunction": "and",
                    "conditions": [{"field_name": "状态", "operator": "contains", "value": ["处理中"]}],
                },
                "createdAfter": "2026-06-24 18:00:00",
            }
        )
        captured_config = {}

        def fake_query_fields(query_config):
            captured_config.update(query_config)
            return [{"field_name": "工单号"}, {"field_name": "描述"}]

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketSyncNotifyService, "query_bitable_fields", side_effect=fake_query_fields),
            patch.object(TicketSyncNotifyService, "query_bitable_records") as query_records,
        ):
            result = TicketBitablePullService.preview_bitable_pull_fields_services(db=SimpleNamespace())

        self.assertEqual(result["source"], "fields")
        self.assertEqual(result["fieldNames"], ["工单号", "描述"])
        self.assertEqual(captured_config["filterFormula"], "")
        self.assertEqual(captured_config["createdAfter"], "")
        query_records.assert_not_called()

    def test_preview_bitable_pull_fields_falls_back_to_unfiltered_sample_record(self):
        """字段元数据读取不可用时，应清空过滤条件后用样例记录推断字段。"""
        config = TicketSyncConfigService.default_sync_config()
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "filterFormula": {
                    "conjunction": "and",
                    "conditions": [{"field_name": "状态", "operator": "contains", "value": ["处理中"]}],
                },
                "createdAfter": "2026-06-24 18:00:00",
            }
        )
        captured_config = {}

        def fake_query_records(query_config):
            captured_config.update(query_config)
            return [{"record_id": "rec_001", "fields": {"工单号": "T-001", "描述": "支付失败"}}]

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketSyncNotifyService, "query_bitable_fields", side_effect=RuntimeError("no scope")),
            patch.object(TicketSyncNotifyService, "query_bitable_records", side_effect=fake_query_records),
        ):
            result = TicketBitablePullService.preview_bitable_pull_fields_services(db=SimpleNamespace())

        self.assertEqual(result["source"], "sample_record")
        self.assertEqual(result["fieldNames"], ["工单号", "描述"])
        self.assertEqual(result["sampleRecordId"], "rec_001")
        self.assertEqual(captured_config["filterFormula"], "")
        self.assertEqual(captured_config["createdAfter"], "")

    def test_query_bitable_records_hydrates_shared_url_from_batch_get(self):
        """搜索接口未返回详情链接时，应通过 batch_get 按 record_id 补齐 shared_url。"""
        config = {
            "appId": "app_id",
            "appSecret": "app_secret",
            "appToken": "app_token",
            "tableId": "tbl_token",
            "viewId": "vew_token",
            "pageSize": 1,
            "filterFormula": "",
        }
        search_response = {
            "data": {
                "items": [
                    {
                        "record_id": "rec_001",
                        "fields": {"工单号": "T-001"},
                    }
                ],
                "has_more": False,
                "page_token": "",
            }
        }
        batch_response = {
            "data": {
                "records": [
                    {
                        "record_id": "rec_001",
                        "shared_url": "https://duodian.feishu.cn/record/FUY1rD5Cte98g0cx6qYcEOTYnBh",
                    }
                ]
            }
        }

        with (
            patch.object(TicketSyncNotifyService, "_resolve_feishu_auth", return_value=("app_id", "app_secret")),
            patch.object(TicketSyncNotifyService, "_get_tenant_access_token", return_value="tenant_token"),
            patch.object(
                TicketSyncNotifyService,
                "_request_feishu_json",
                side_effect=[search_response, batch_response],
            ),
        ):
            records = TicketSyncNotifyService.query_bitable_records(config)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["record_id"], "rec_001")
        self.assertEqual(
            records[0]["shared_url"],
            "https://duodian.feishu.cn/record/FUY1rD5Cte98g0cx6qYcEOTYnBh",
        )

    def test_query_bitable_records_sends_pagination_in_query_params(self):
        """查询多维表格记录时，分页参数应放在 URL 查询参数中，避免飞书忽略分页设置。"""
        config = {
            "appId": "app_id",
            "appSecret": "app_secret",
            "appToken": "app_token",
            "tableId": "tbl_token",
            "viewId": "vew_token",
            "pageSize": 200,
            "filterFormula": {"conjunction": "and", "conditions": []},
        }
        first_response = {
            "data": {
                "items": [{"record_id": "rec_001", "fields": {}, "shared_url": "https://example.com/rec_001"}],
                "has_more": True,
                "page_token": "token_200",
            }
        }
        second_response = {
            "data": {
                "items": [{"record_id": "rec_002", "fields": {}, "shared_url": "https://example.com/rec_002"}],
                "has_more": False,
                "page_token": "",
            }
        }

        with (
            patch.object(TicketSyncNotifyService, "_resolve_feishu_auth", return_value=("app_id", "app_secret")),
            patch.object(TicketSyncNotifyService, "_get_tenant_access_token", return_value="tenant_token"),
            patch.object(
                TicketSyncNotifyService,
                "_request_feishu_json",
                side_effect=[first_response, second_response],
            ) as request_json,
        ):
            records = TicketSyncNotifyService.query_bitable_records(config)

        self.assertEqual([item["record_id"] for item in records], ["rec_001", "rec_002"])
        first_call = request_json.call_args_list[0].kwargs
        second_call = request_json.call_args_list[1].kwargs
        self.assertEqual(first_call["params"]["page_size"], 200)
        self.assertNotIn("page_size", first_call["json_body"])
        self.assertNotIn("page_token", first_call["json_body"])
        self.assertEqual(second_call["params"]["page_size"], 200)
        self.assertEqual(second_call["params"]["page_token"], "token_200")
        self.assertNotIn("page_token", second_call["json_body"])

    def test_query_bitable_records_stops_on_repeated_page_token(self):
        """飞书返回重复分页令牌时，应停止拉取避免同一页无限循环。"""
        config = {
            "appId": "app_id",
            "appSecret": "app_secret",
            "appToken": "app_token",
            "tableId": "tbl_token",
            "viewId": "vew_token",
            "pageSize": 200,
            "filterFormula": "",
        }
        first_response = {
            "data": {
                "items": [{"record_id": "rec_001", "fields": {}, "shared_url": "https://example.com/rec_001"}],
                "has_more": True,
                "page_token": "same_token",
            }
        }
        repeated_response = {
            "data": {
                "items": [{"record_id": "rec_001_dup", "fields": {}, "shared_url": "https://example.com/rec_001_dup"}],
                "has_more": True,
                "page_token": "same_token",
            }
        }

        with (
            patch.object(TicketSyncNotifyService, "_resolve_feishu_auth", return_value=("app_id", "app_secret")),
            patch.object(TicketSyncNotifyService, "_get_tenant_access_token", return_value="tenant_token"),
            patch.object(
                TicketSyncNotifyService,
                "_request_feishu_json",
                side_effect=[first_response, repeated_response, repeated_response],
            ) as request_json,
        ):
            records = TicketSyncNotifyService.query_bitable_records(config)

        self.assertEqual([item["record_id"] for item in records], ["rec_001", "rec_001_dup"])
        self.assertEqual(request_json.call_count, 2)

    def test_bitable_pull_override_adds_default_created_after(self):
        """主动拉取任务未指定时间时，应默认查询当前时间前 1 小时后的记录。"""
        before_call = datetime.now() - timedelta(hours=1, seconds=2)
        config = TicketSyncConfigService.default_sync_config()
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "fieldMappings": [{"sourceField": "工单号", "targetField": "ticketNo"}],
            }
        )

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketSyncConfigService, "iter_bitable_pull_records", return_value=[]),
        ):
            result = TicketBitablePullService.run_bitable_pull_services(
                db=SimpleNamespace(),
                trigger_source="test",
                bitable_pull_override=_build_bitable_pull_config_override({}),
            )

        after_call = datetime.now() - timedelta(hours=1) + timedelta(seconds=2)
        created_after = datetime.strptime(result["createdAfter"], "%Y-%m-%d %H:%M:%S")
        self.assertFalse(result["skipped"])
        self.assertGreaterEqual(created_after, before_call.replace(microsecond=0))
        self.assertLessEqual(created_after, after_call.replace(microsecond=0))

    def test_bitable_pull_auto_append_ignores_specified_created_after(self):
        """自动追加时间窗口开启时，应忽略显式时间并沿用拆分前的最近 1 小时窗口。"""
        before_call = datetime.now() - timedelta(hours=1, seconds=2)
        config = TicketSyncConfigService.default_sync_config()
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "fieldMappings": [{"sourceField": "工单号", "targetField": "ticketNo"}],
            }
        )

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketSyncConfigService, "iter_bitable_pull_records", return_value=[]),
        ):
            result = TicketBitablePullService.run_bitable_pull_services(
                db=SimpleNamespace(),
                trigger_source="test",
                bitable_pull_override=_build_bitable_pull_config_override({"created_after": "2026-06-22 10:48:00"}),
            )

        after_call = datetime.now() - timedelta(hours=1) + timedelta(seconds=2)
        created_after = datetime.strptime(result["createdAfter"], "%Y-%m-%d %H:%M:%S")
        self.assertFalse(result["skipped"])
        self.assertGreaterEqual(created_after, before_call.replace(microsecond=0))
        self.assertLessEqual(created_after, after_call.replace(microsecond=0))

    def test_bitable_pull_force_sync_bypasses_snapshot_skip(self):
        """强制同步时应忽略 snapshotHash 去重并重新调用外部同步入库。"""
        config = TicketSyncConfigService.default_sync_config()
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "fieldMappings": [
                    {"sourceField": "工单号", "targetField": "ticketNo"},
                    {"sourceField": "描述", "targetField": "description"},
                    {"sourceField": "优先级", "targetField": "internalPriority"},
                    {"sourceField": "项目", "targetField": "projectName"},
                    {"sourceField": "模块", "targetField": "moduleName"},
                    {"sourceField": "提单人", "targetField": "reporterName"},
                    {"sourceField": "创建时间", "targetField": "createTime"},
                ],
                "forceSync": True,
            }
        )
        record = {
            "record_id": "rec_force",
            "fields": {
                "工单号": "T-FORCE",
                "描述": "Checkout failed",
                "优先级": "P2",
                "项目": "海外收银",
                "模块": "POS - 支付",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }
        existing_ticket = SimpleNamespace(
            extra_data={"bitable_pull": {"recordId": "rec_force", "snapshotHash": "same"}}
        )

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketSyncConfigService, "iter_bitable_pull_records", return_value=[record]),
            patch.object(
                TicketBitablePullService,
                "should_skip_bitable_pull_record",
                return_value=(True, "snapshot_not_changed"),
            ) as skip_check,
            patch.object(
                TicketSyncPostProcessService,
                "dispatch_deferred_sync_post_process_task",
                return_value={"mode": "celery"},
            ),
            patch.object(
                TicketSyncService,
                "sync_external_ticket",
                return_value=SimpleNamespace(is_success=True),
            ) as sync_external,
            patch(
                "modules.ticket.service.sync.ticket_bitable_pull_service.TicketDao.get_ticket_by_no",
                return_value=existing_ticket,
            ),
        ):
            result = TicketBitablePullService.run_bitable_pull_services(
                db=SimpleNamespace(),
                trigger_source="test",
                bitable_pull_override=_build_bitable_pull_config_override({"forceSync": True}),
            )

        skip_check.assert_not_called()
        sync_external.assert_called_once()
        self.assertIsNone(sync_external.call_args.args[1].automation)
        self.assertTrue(result["forceSync"])
        self.assertEqual(result["syncedCount"], 1)
        self.assertEqual(result["skippedCount"], 0)

    def test_bitable_pull_uses_external_field_model_required_fields_before_ingest(self):
        """主动拉取应按外部工单字段模型必填项校验，字段不全时不入库也不触发后处理。"""
        config = TicketSyncConfigService.default_sync_config()
        config["externalFieldModel"] = {
            "fields": [
                {"fieldName": "ticketNo", "label": "工单号", "required": True},
                {"fieldName": "description", "label": "描述", "required": True},
                {"fieldName": "internalPriority", "label": "内部优先级", "required": True},
                {"fieldName": "ticketVender", "label": "项目", "required": True},
                {"fieldName": "ticketModle", "label": "模块", "required": True},
                {"fieldName": "createTime", "label": "创建时间", "required": True},
                {"fieldName": "reporterName", "label": "提单人", "required": True},
            ]
        }
        config["externalSyncRequiredFields"] = ["ticketNo", "description"]
        config["bitablePull"].update(
            {
                "enabled": True,
                "appId": "app_id",
                "appSecret": "app_secret",
                "appToken": "app_token",
                "tableId": "table_id",
                "fieldMappings": [
                    {"sourceField": "工单号", "targetField": "ticketNo"},
                    {"sourceField": "描述", "targetField": "description"},
                    {"sourceField": "优先级", "targetField": "internalPriority"},
                    {"sourceField": "项目", "targetField": "projectName"},
                    {"sourceField": "提单人", "targetField": "reporterName"},
                    {"sourceField": "创建时间", "targetField": "createTime"},
                ],
            }
        )
        record = {
            "record_id": "rec_missing_module",
            "fields": {
                "工单号": "T-MISSING-MODULE",
                "描述": "Checkout failed",
                "优先级": "P2",
                "项目": "海外收银",
                "提单人": "张三",
                "创建时间": "2026-06-24 09:59:00",
            },
        }

        with (
            patch.object(
                TicketSyncConfigService,
                "load_sync_config",
                return_value=TicketSyncConfigService.normalize_sync_config(config),
            ),
            patch.object(TicketSyncConfigService, "iter_bitable_pull_records", return_value=[record]),
            patch.object(TicketSyncService, "sync_external_ticket") as sync_external,
            patch.object(TicketSyncPostProcessService, "dispatch_deferred_sync_post_process_task") as dispatch_deferred,
        ):
            result = TicketBitablePullService.run_bitable_pull_services(
                db=SimpleNamespace(),
                trigger_source="test",
                bitable_pull_override=_build_bitable_pull_config_override({"createdAfter": "2026-06-24 00:00:00"}),
            )

        sync_external.assert_not_called()
        dispatch_deferred.assert_not_called()
        self.assertEqual(result["syncedCount"], 0)
        self.assertEqual(result["failedCount"], 1)
        self.assertEqual(result["failures"][0]["recordId"], "rec_missing_module")
        self.assertEqual(result["failures"][0]["reason"], "record_to_sync_object_failed")

    def test_external_sync_uses_automation_translate_switch_when_present(self):
        """外部同步传入自动化配置时，翻译开关应优先使用本次场景配置。"""
        sync_object = TicketBitablePullService.build_bitable_pull_sync_object(
            record={
                "record_id": "rec_translate",
                "fields": {
                    "工单号": "T-TRANS",
                    "描述": "Checkout failed",
                    "优先级": "P2",
                    "项目": "海外收银",
                    "模块": "POS - 支付",
                    "提单人": "张三",
                    "创建时间": "2026-06-24 09:59:00",
                },
            },
            config={"sourceSystem": "feishu_bitable_pull"},
            field_mappings=TicketSyncConfigService.normalize_bitable_field_mappings(
                [
                    {"sourceField": "工单号", "targetField": "ticketNo"},
                    {"sourceField": "描述", "targetField": "description"},
                    {"sourceField": "优先级", "targetField": "internalPriority"},
                    {"sourceField": "项目", "targetField": "projectName"},
                    {"sourceField": "模块", "targetField": "moduleName"},
                    {"sourceField": "提单人", "targetField": "reporterName"},
                    {"sourceField": "创建时间", "targetField": "createTime"},
                ]
            ),
        )
        sync_object = sync_object.model_copy(
            update={
                "automation": TicketSyncAutomationModel.model_validate({
                    "autoIdentify": False,
                    "autoLogPull": False,
                    "autoAiAnalysis": False,
                    "autoTranslate": True,
                })
            }
        )
        current_user = CurrentUserModel.model_validate(TicketBitablePullService.build_system_current_user_payload())

        with (
            patch.object(
                TicketSyncConfigService,
                "load_sync_config",
                return_value={
                    **TicketSyncConfigService.default_sync_config(),
                    "autoTranslateOnSync": False,
                    "externalSyncBitable": {"enabled": False},
                },
            ),
            patch.object(TicketSyncAutomationService, "detect_fields", return_value={}),
            patch.object(TicketSyncService, "_translate_sync_description") as translate_description,
            patch.object(TicketSyncPayloadService, "build_upsert_payload", return_value=({}, {}, 1)),
            patch.object(TicketSyncCommentService, "sync_step_reason_comments", return_value={}),
            patch.object(
                TicketAutoClassificationService,
                "run_auto_ticket_ai_classification",
                side_effect=lambda _db, ticket, **_kwargs: (ticket, {}),
            ),
            patch.object(TicketSyncAutomationService, "run_sync_automation", return_value={}),
            patch.object(
                TicketSyncGroupPushService,
                "finalize_publish_state_after_post_process",
                side_effect=lambda _db, ticket, **_kwargs: (ticket, {}, None),
            ),
            patch.object(TicketSyncDeliveryService, "extract_sync_summary", return_value={}),
            patch.object(TicketSyncService, "_resolve_sync_title", return_value=("T-TRANS", {"mode": "raw"})),
            patch.object(
                TicketExternalBitableEmailService,
                "enrich_person_emails",
                side_effect=lambda _c, obj, _t: obj,
            ),
            patch.object(TicketLightAiService, "is_translation_enabled", return_value=True),
            patch.object(TicketLightAiService, "extract_ticket_sync_fields", return_value=({}, {"skipped": True})),
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.get_ticket_by_no", return_value=None),
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.add_ticket") as add_ticket,
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.add_status_history"),
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.add_message"),
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.add_event"),
            patch("modules.ticket.service.sync.ticket_sync_service.TicketDao.get_ticket_by_id") as get_ticket_by_id,
            patch(
                "modules.ticket.service.sync.ticket_sync_service.TicketService.get_ticket_detail_services",
                return_value={"ticketId": 1, "extraData": {}},
            ),
        ):
            ticket = SimpleNamespace(
                ticket_id=1,
                extra_data={},
                title="T-TRANS",
                description="已翻译",
                status="pending",
            )
            add_ticket.return_value = ticket
            get_ticket_by_id.return_value = ticket
            translate_description.return_value = (
                "结账失败",
                {"translated_text": "结账失败"},
                "Checkout failed",
            )

            result = TicketSyncService.sync_external_ticket(
                db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
                sync_object=sync_object,
                current_user=current_user,
                sync_scene="external_sync",
                defer_post_process=False,
            )

        self.assertTrue(result.is_success)
        translate_description.assert_called_once()
        self.assertTrue(translate_description.call_args.kwargs["enabled"])

    def test_system_current_user_payload_matches_current_user_model(self):
        """后台系统用户载荷应满足 CurrentUserModel 校验，避免 Celery 反序列化失败。"""
        payload = TicketBitablePullService.build_system_current_user_payload()

        current_user = CurrentUserModel.model_validate(payload)

        self.assertEqual(current_user.permissions, [])
        self.assertEqual(current_user.roles, [])
        self.assertEqual(current_user.user.user_id, 0)
        self.assertEqual(current_user.user.user_name, "system")

    def test_deferred_current_user_payload_accepts_legacy_user_only_payload(self):
        """延后后处理应兼容历史只包含 user 的任务载荷。"""
        payload = TicketSyncPostProcessService.normalize_current_user_payload(
            {"user": {"user_id": 0, "user_name": "system", "nick_name": "system"}}
        )

        current_user = CurrentUserModel.model_validate(payload)

        self.assertEqual(current_user.permissions, [])
        self.assertEqual(current_user.roles, [])
        self.assertEqual(current_user.user.user_id, 0)
        self.assertEqual(current_user.user.user_name, "system")

    def test_bitable_pull_person_mapping_extracts_name_and_email(self):
        """主动拉取人员字段应从飞书人员对象中分别提取姓名和邮箱。"""
        fields = {
            "提单人": [{"name": "张三", "email": "zhangsan@example.com"}],
            "当前负责人": [{"name": "李四", "email": "lisi@example.com"}],
        }

        payload = FeishuBitableUtil.build_pull_field_mapping_from_record(
            fields,
            field_mappings=[
                {"sourceField": "提单人", "targetField": "reporterName"},
                {"sourceField": "提单人", "targetField": "reporterEmail"},
                {"sourceField": "当前负责人", "targetField": "currentAssigneeName"},
                {"sourceField": "当前负责人", "targetField": "currentAssigneeEmail"},
            ],
        )

        self.assertEqual(payload["reporterName"], "张三")
        self.assertEqual(payload["reporterEmail"], "zhangsan@example.com")
        self.assertEqual(payload["currentAssigneeName"], "李四")
        self.assertEqual(payload["currentAssigneeEmail"], "lisi@example.com")

    def test_notify_email_extracts_nested_person_payload(self):
        """群消息 @ 人邮箱解析应兼容飞书人员对象和数组。"""
        email = TicketSyncNotifyService._extract_email_from_payload(
            {
                "currentAssigneeEmail": [
                    {"name": "李四", "email": "lisi@example.com"},
                    {"name": "王五", "email": "wangwu@example.com"},
                ],
            },
            ["currentAssigneeEmail"],
        )

        self.assertEqual(email, "lisi@example.com")

    def test_group_template_assignee_variables_fallback_to_internal_owner(self):
        """群消息模板当前处理人变量为空时，应使用内部负责人作为展示兜底。"""
        ticket = SimpleNamespace(
            ticket_id=1,
            ticket_no="T-GROUP-FALLBACK",
            title="群消息兜底",
            merchant_name="海外收银",
            module_name="POS",
            status="processing",
            reporter_name="张三",
            first_line_assignee_name="",
            current_assignee_name="",
            internal_owner_name="王五",
            customer_priority="Level B",
            internal_priority="P2",
            source="external_sync",
            description="描述",
            ticket_url="",
            extra_data={},
        )

        variables = TicketSyncNotifyService._build_group_ticket_variables(ticket)

        self.assertEqual(variables["assignee_name"], "王五")
        self.assertEqual(variables["current_assignee_name"], "王五")
        self.assertEqual(variables["currentAssigneeName"], "王五")
        self.assertEqual(variables["raw_assignee_name"], "-")

    def test_group_template_assignee_at_fallback_to_internal_owner_at(self):
        """群消息模板当前处理人 @ 为空时，应使用内部负责人 @ 兜底。"""
        variables = TicketSyncNotifyService._build_group_mention_template_variables(
            [{"role": "internal_owner", "openId": "ou_owner"}]
        )

        self.assertEqual(variables["assignee_at"], '<at user_id="ou_owner"></at>')
        self.assertEqual(variables["current_assignee_at"], '<at user_id="ou_owner"></at>')
        self.assertEqual(variables["internal_owner_at"], '<at user_id="ou_owner"></at>')

    def test_batch_reclassification_service_runs_regex_batch_entry(self):
        """批量重归类入口应由独立服务编排，不再回到 TicketSyncService。"""
        ticket = SimpleNamespace(
            ticket_id=1001,
            ticket_no="TK-RECLASS",
            title="支付失败",
            description="用户反馈扣款异常",
        )
        db = SimpleNamespace(query=lambda *_args, **_kwargs: _TicketListQuery([ticket]))
        request = SimpleNamespace(
            strategy="regex",
            regex_rules=[{"pattern": "支付|扣款", "category": "支付问题"}],
            only_uncategorized=False,
            all_tickets=True,
            force_reclassify=True,
            page_num=1,
            page_size=100,
            ticket_nos=None,
            ai_prompt_code=None,
        )
        current_user = SimpleNamespace(user=SimpleNamespace(user_name="tester", nick_name=""))

        with patch.object(
            TicketBatchReclassificationService,
            "run_auto_ticket_category_classification",
            return_value=(ticket, {"skipped": False, "categoryName": "支付问题"}),
        ) as run_category:
            result = TicketBatchReclassificationService.batch_reclassify_ticket_categories_services(
                db,
                request,
                current_user,
            )

        run_category.assert_called_once()
        self.assertEqual(result["selectedCount"], 1)
        self.assertEqual(result["successCount"], 1)
        self.assertEqual(result["details"][0]["categoryName"], "支付问题")

    def test_external_sync_request_service_normalizes_person_fields_and_raw_payload(self):
        """外部请求归一化应保留原始载荷，并从人员文本提取姓名和邮箱。"""
        payload = {
            "ticketNo": "EXT-NORMALIZE",
            "description": "无法结账",
            "internalPriority": "P1",
            "ticketVender": "海外收银",
            "ticketModle": "POS",
            "createTime": "2026-07-04 12:00:00",
            "reporterName": {"name": "张三", "email": "zhangsan@example.com"},
            "currentAssigneeName": {"name": "李四", "email": "lisi@example.com"},
            "internalOwner": {"name": "王五", "email": "wangwu@example.com"},
            "ticketUrl": "https://example.com/ticket/1",
            "stepReason": "20260704 张三：初步排查",
        }

        normalized = TicketExternalSyncRequestService.normalize_external_sync_payload(payload)

        self.assertEqual(normalized["ticketNo"], "EXT-NORMALIZE")
        self.assertEqual(normalized["reporterName"], "张三")
        self.assertEqual(normalized["reporterEmail"], "zhangsan@example.com")
        self.assertEqual(normalized["currentAssigneeName"], "李四")
        self.assertEqual(normalized["internalOwnerName"], "王五")
        self.assertEqual(normalized["source"]["recordId"], "EXT-NORMALIZE")
        self.assertEqual(normalized["source"]["recordUrl"], "https://example.com/ticket/1")
        self.assertEqual(normalized["raw_payload"]["reporterName"]["name"], "张三")
        external_mapping = normalized["extraData"]["external_field_mapping"]
        self.assertEqual(external_mapping["currentAssigneeEmail"], "lisi@example.com")
        self.assertEqual(external_mapping["internalOwnerEmail"], "wangwu@example.com")
        self.assertEqual(normalized["extraData"]["step_reason"], "20260704 张三：初步排查")

    def test_external_sync_request_service_converts_customer_priority_when_internal_missing(self):
        """外部推送只有对方优先级时，应按 Level 到 P 的关系补齐内部优先级。"""
        payload = {
            "ticketNo": "EXT-PRIORITY",
            "description": "无法结账",
            "customerPriority": "Level A",
            "ticketVender": "海外收银",
            "ticketModle": "POS",
            "createTime": "2026-07-21 12:00:00",
            "reporterName": "张三",
        }

        normalized = TicketExternalSyncRequestService.normalize_external_sync_payload(payload)

        self.assertEqual(normalized["customerPriority"], "Level A")
        self.assertEqual(normalized["internalPriority"], "P1")
        self.assertEqual(normalized["extraData"]["external_field_mapping"]["customerPriority"], "Level A")
        self.assertEqual(normalized["extraData"]["external_field_mapping"]["internalPriority"], "P1")

    def test_external_sync_request_service_converts_internal_priority_when_customer_missing(self):
        """外部推送只有内部优先级时，应按 P 到 Level 的关系补齐对方优先级。"""
        payload = {
            "ticketNo": "EXT-PRIORITY-INTERNAL",
            "description": "无法结账",
            "internalPriority": "P0",
            "ticketVender": "海外收银",
            "ticketModle": "POS",
            "createTime": "2026-07-21 12:00:00",
            "reporterName": "张三",
        }

        normalized = TicketExternalSyncRequestService.normalize_external_sync_payload(payload)

        self.assertEqual(normalized["customerPriority"], "Level 0")
        self.assertEqual(normalized["internalPriority"], "P0")

    def test_external_sync_request_service_validates_required_fields(self):
        """外部请求归一化应按配置必填字段提前拒绝缺失载荷。"""
        with self.assertRaisesRegex(ValueError, "ticketNo"):
            TicketExternalSyncRequestService.normalize_external_sync_payload(
                {"description": "缺少工单号"},
                required_fields=["ticketNo", "description"],
            )

    def test_bitable_pull_records_filter_builds_default_cloud_time_filter(self):
        """主动拉取应构造飞书云端更新时间过滤条件（仅更新时间字段）。"""
        filter_millis = TicketSyncConfigService.datetime_to_bitable_filter_millis(datetime(2026, 6, 22, 10, 48, 0))

        filters = TicketSyncConfigService.build_bitable_pull_time_filters(
            filter_formula="",
            created_after=datetime(2026, 6, 22, 10, 48, 0),
            updated_at_field="更新时间",
        )

        self.assertEqual(
            filters,
            [
                {
                    "conjunction": "and",
                    "conditions": [
                        {
                            "field_name": "更新时间",
                            "operator": "isGreater",
                            "value": ["ExactDate", f"{filter_millis}"],
                        },
                    ],
                }
            ],
        )

    def test_bitable_pull_time_filter_nested_appends_outer_child(self):
        """嵌套 filter 应沿用拆分前语义，只在最外层 children 追加时间范围。"""
        created_after = datetime(2026, 6, 24, 0, 59, 0)
        filter_millis = TicketSyncConfigService.datetime_to_bitable_filter_millis(created_after)
        filter_formula = {
            "conjunction": "and",
            "children": [
                {
                    "conjunction": "and",
                    "conditions": [
                        {"field_name": "更新时间", "operator": "isGreaterEqual", "value": ""},
                        {"field_name": "状态", "operator": "contains", "value": ["待处理"]},
                    ],
                },
                {
                    "conjunction": "or",
                    "children": [
                        {
                            "conjunction": "and",
                            "conditions": [
                                {"field_name": "创建时间", "operator": "isGreater", "value": []},
                            ],
                        }
                    ],
                },
            ],
        }

        filters = TicketSyncConfigService.build_bitable_pull_time_filters(
            filter_formula=filter_formula,
            created_after=created_after,
            updated_at_field="更新时间",
        )

        self.assertEqual(len(filters), 1)
        children = filters[0]["children"]
        self.assertEqual(len(children), 3)
        self.assertEqual(children[0]["conditions"][0]["value"], "")
        self.assertEqual(children[2]["conjunction"], "and")
        self.assertEqual(
            [condition["field_name"] for condition in children[2]["conditions"]],
            ["更新时间"],
        )
        self.assertEqual(children[2]["conditions"][0]["value"], ["ExactDate", f"{filter_millis}"])

    def test_bitable_pull_time_filter_flat_keeps_configured_filter(self):
        """扁平 filter 应沿用拆分前语义，存在配置 filter 时不追加默认时间范围。"""
        created_after = datetime(2026, 6, 24, 0, 59, 0)
        filter_formula = {
            "conjunction": "and",
            "conditions": [
                {"field_name": "更新时间", "operator": "isGreaterEqual", "value": ""},
                {"field_name": "状态", "operator": "contains", "value": ["待处理"]},
            ],
        }

        filters = TicketSyncConfigService.build_bitable_pull_time_filters(
            filter_formula=filter_formula,
            created_after=created_after,
            updated_at_field="更新时间",
        )

        self.assertEqual(len(filters), 1)
        self.assertNotIn("children", filters[0])
        self.assertEqual(len(filters[0]["conditions"]), 2)
        self.assertEqual(filters[0]["conditions"][0]["value"], "")
        self.assertEqual(filters[0]["conditions"][1]["value"], ["待处理"])

    def test_feishu_message_sync_resolves_sender_open_id_to_user_name(self):
        """飞书消息同步应把发送人 open_id 查询成用户名后再写入评论和多维排查过程。"""
        config = TicketSyncConfigService.default_sync_config()
        config["feishuAuth"].update({"appId": "app_id", "appSecret": "app_secret"})
        config["bitablePull"].update({"appId": "bitable_app_id", "appSecret": "bitable_app_secret"})
        config["groupPush"].update({"appId": "group_app_id", "appSecret": "group_app_secret"})
        config["messageSync"].update(
            {
                "enabled": True,
                "feishuEventEnabled": True,
                "syncFeishuCommentToTicket": True,
                "syncFeishuCommentToBitable": True,
            }
        )
        ticket = SimpleNamespace(
            ticket_id=1001,
            ticket_no="TK1001",
            extra_data={
                TicketSyncPayloadService.META_KEY: {
                    "sync_state": {
                        "group_push_message_refs": [
                            {
                                "chatId": "oc_chat",
                                "messageId": "om_root",
                                "rootId": "om_root",
                                "threadId": "omt_thread",
                            }
                        ]
                    }
                },
                "bitable_pull": {"recordId": "rec_001"},
            },
        )
        payload = {
            "header": {"event_id": "evt_001", "create_time": "1790000000000"},
            "event": {
                "sender": {
                    "sender_id": {
                        "open_id": "ou_sender",
                        "union_id": "on_union",
                    }
                },
                "message": {
                    "message_id": "om_comment",
                    "root_id": "om_root",
                    "thread_id": "omt_thread",
                    "parent_id": "om_root",
                    "chat_id": "oc_chat",
                    "message_type": "text",
                    "content": '{"text":"请 @_user_1 协助排查"}',
                    "mentions": [
                        {
                            "key": "@_user_1",
                            "id": {"open_id": "ou_ken", "union_id": "on_ken", "user_id": "u_ken"},
                            "name": "Ken Pong",
                        }
                    ],
                },
            },
        }

        with (
            patch.object(TicketSyncConfigService, "load_sync_config", return_value=config),
            patch.object(TicketMessageSyncService, "_match_ticket_by_message_context", return_value=ticket),
            patch.object(
                TicketSyncNotifyService,
                "query_feishu_user_by_open_id",
                return_value={"openId": "ou_sender", "name": "张三"},
            ) as query_user,
            patch.object(TicketMessageSyncService, "append_comment_to_bitable_step_reason") as append_bitable,
            patch(
                "modules.ticket.service.collaboration.ticket_message_sync_service."
                "TicketCommentCoreService.upsert_synced_comment"
            ) as upsert,
        ):
            upsert.return_value = (SimpleNamespace(id=88), "created")
            append_bitable.return_value = {"skipped": False, "recordId": "rec_001"}
            result = TicketMessageSyncService.handle_feishu_message_event(
                SimpleNamespace(commit=lambda: None),
                payload,
            )

        self.assertFalse(result["skipped"])
        query_user.assert_called_once_with(app_id="app_id", app_secret="app_secret", open_id="ou_sender")
        self.assertEqual(upsert.call_args.kwargs["user_name"], "张三")
        self.assertEqual(upsert.call_args.kwargs["content"], "请 @Ken Pong 协助排查")
        self.assertEqual(upsert.call_args.kwargs["attachments"]["mentions"][0]["openId"], "ou_ken")
        self.assertEqual(upsert.call_args.kwargs["attachments"]["content_segments"][1]["openId"], "ou_ken")
        self.assertEqual(append_bitable.call_args.kwargs["user_name"], "张三")
        self.assertEqual(append_bitable.call_args.kwargs["content_segments"][1]["openId"], "ou_ken")


class _EmptyQuery:
    """提供最小查询链，避免单元测试依赖真实数据库。"""

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _TicketListQuery:
    """提供批量重归类测试需要的最小列表查询链。"""

    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def offset(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def count(self):
        return len(self.rows)

    def all(self):
        return list(self.rows)


class _ModelQueryDb:
    """按模型类型返回最小查询链，避免单元测试依赖真实数据库。"""

    def __init__(self, *, project=None, module=None):
        self.project = project
        self.module = module

    def query(self, model, *_args, **_kwargs):
        model_name = getattr(model, "__name__", "")
        if model_name == "HrmProject":
            return _SingleRowQuery(self.project)
        if model_name == "HrmModule":
            return _SingleRowQuery(self.module)
        return _EmptyQuery()


class _SingleRowQuery:
    """提供单条记录查询链。"""

    def __init__(self, row):
        self.row = row

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.row


if __name__ == "__main__":
    unittest.main()


