"""指定工单手动自动化服务单元测试。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.entity.vo.ticket_vo import TicketExternalSyncUpsertModel
from modules.ticket.service.sync.ticket_manual_automation_service import TicketManualAutomationService


class TicketManualAutomationServiceTests(unittest.TestCase):
    """验证手动补跑不会受定时任务开关影响，也不会覆盖数据库快照。"""

    def test_resolve_ticket_no_field_prefers_explicit_field(self):
        """显式配置的飞书工单号字段应优先于字段映射。"""
        field_name = TicketManualAutomationService.resolve_ticket_no_field(
            {
                "ticketNoField": "工单编号",
                "fieldMappings": [{"sourceField": "映射工单号", "targetField": "ticketNo"}],
            }
        )

        self.assertEqual(field_name, "工单编号")

    def test_run_bitable_replay_ignores_enabled_and_uses_ticket_filter(self):
        """手动飞书补跑应忽略 enabled=false，并仅使用指定工单号过滤。"""
        sync_object = TicketExternalSyncUpsertModel.model_validate(
            {
                "ticketNo": "MANUAL-001",
                "title": "手动补跑工单",
                "source": {"system": "feishu_bitable_pull", "recordId": "rec_manual"},
            }
        )
        pull_config = {
            "enabled": False,
            "pageSize": 200,
            "ticketNoField": "工单号",
            "fieldMappings": [{"sourceField": "工单号", "targetField": "ticketNo"}],
        }

        with (
            patch.object(
                TicketManualAutomationService,
                "build_manual_bitable_config",
                return_value=({"externalFieldModel": {}}, pull_config),
            ),
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketSyncConfigService.iter_bitable_pull_records",
                return_value=iter([{"record_id": "rec_manual", "fields": {"工单号": "MANUAL-001"}}]),
            ) as iter_records,
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketBitablePullService.build_bitable_pull_sync_object",
                return_value=sync_object,
            ),
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketSyncService.sync_external_ticket",
                return_value=SimpleNamespace(is_success=True, message="同步成功"),
            ) as sync_ticket,
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketSyncPostProcessService.execute_deferred_sync_post_process"
            ) as post_process,
        ):
            result = TicketManualAutomationService.run_bitable_replay(
                SimpleNamespace(),
                "MANUAL-001",
                SimpleNamespace(),
            )

        self.assertTrue(result["synced"])
        self.assertEqual(result["recordId"], "rec_manual")
        self.assertEqual(pull_config["createdAfter"], "")
        self.assertFalse(pull_config["autoAppendTimeFilter"])
        filter_formula = iter_records.call_args.args[1][0]
        self.assertEqual(filter_formula["conditions"][0]["field_name"], "工单号")
        self.assertEqual(filter_formula["conditions"][0]["value"], ["MANUAL-001"])
        sync_ticket.assert_called_once()
        post_process.assert_called_once()

    def test_database_replay_does_not_call_external_sync(self):
        """数据库快照模式只执行后处理，不能重新调用外部同步入库。"""
        ticket = SimpleNamespace(
            ticket_no="DB-001",
            ticket_url="https://example.test/tickets/DB-001",
            title="数据库快照工单",
            description="已存在的工单描述",
            project_id=None,
            merchant_name="示例商家",
            module_id=None,
            module_code="PAY",
            module_name="支付",
            category_id=None,
            category_name="",
            issue_type_id="",
            issue_type_name="",
            status="processing",
            customer_priority="P2",
            internal_priority="P2",
            severity="",
            reporter_id=None,
            reporter_name="提单人",
            current_assignee_id=None,
            current_assignee_name="处理人",
            internal_owner_id=None,
            internal_owner_name="负责人",
            is_problem=True,
            root_cause_type="",
            solution_type="",
            resolution_code="",
            resolution_name="",
            submit_time=None,
            update_time=None,
            extra_data={"bitable_pull": {"recordId": "rec_db"}},
        )

        with (
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service.TicketDao.get_ticket_by_no",
                return_value=ticket,
            ),
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketSyncPostProcessService.execute_deferred_sync_post_process"
            ) as post_process,
            patch(
                "modules.ticket.service.sync.ticket_manual_automation_service."
                "TicketSyncService.sync_external_ticket"
            ) as sync_ticket,
        ):
            result = TicketManualAutomationService.run_database_replay(
                SimpleNamespace(),
                "DB-001",
                SimpleNamespace(),
            )

        self.assertFalse(result["synced"])
        self.assertTrue(result["postProcessExecuted"])
        sync_ticket.assert_not_called()
        replay_object = post_process.call_args.args[1]
        self.assertEqual(replay_object.ticket_no, "DB-001")
        self.assertEqual(replay_object.source.system, "manual_database_replay")
        self.assertEqual(replay_object.extra_data["manual_automation_replay"]["source"], "database")


if __name__ == "__main__":
    unittest.main()
