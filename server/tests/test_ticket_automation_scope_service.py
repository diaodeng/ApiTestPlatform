"""工单同步自动化关注范围的定向测试。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.stats.ticket_processing_stats_service import TicketProcessingStatsService
from modules.ticket.service.sync.ticket_automation_scope_service import TicketAutomationScopeService
from modules.ticket.service.sync.ticket_sync_group_push_service import TicketSyncGroupPushService


class TicketAutomationScopeServiceTests(unittest.TestCase):
    """验证关注范围判定、审计和统计模块范围合并规则。"""

    def test_module_name_keyword_allows_automation(self):
        """模块名称包含关键字时应允许进入自动化范围并记录命中依据。"""
        decision = TicketAutomationScopeService.evaluate_module(
            {
                "automationScope": {
                    "enabled": True,
                    "moduleIds": [],
                    "moduleNameIncludes": ["POS"],
                }
            },
            module_id=101,
            module_name="POS-收银台",
        )

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.matched_by, "module_name_contains")
        self.assertEqual(decision.matched_value, "POS")

    def test_unmatched_module_skips_automation_and_preserves_audit(self):
        """启用范围后未命中模块应被排除，且审计字段保留模块和原因。"""
        decision = TicketAutomationScopeService.evaluate_module(
            {
                "automationScope": {
                    "enabled": True,
                    "moduleIds": [99],
                    "moduleNameIncludes": ["POS"],
                }
            },
            module_id=101,
            module_name="库存中心",
        )
        extra_data = TicketAutomationScopeService.attach_audit_data({"external_field_mapping": {}}, decision)

        self.assertFalse(decision.eligible)
        self.assertEqual(decision.matched_by, "unmatched")
        self.assertEqual(extra_data["automation_scope"]["module_name"], "库存中心")
        self.assertIn("evaluated_at", extra_data["automation_scope"])

    def test_disabled_scope_keeps_historical_automation_behavior(self):
        """未启用关注范围时任意模块都应保留原有自动化行为。"""
        decision = TicketAutomationScopeService.evaluate_module(
            {"automationScope": {"enabled": False}},
            module_id=101,
            module_name="库存中心",
        )

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.matched_by, "scope_disabled")

    def test_enabled_scope_without_conditions_keeps_all_modules(self):
        """启用范围但未配置模块条件时应保持不限制，避免空配置误拦截所有自动化。"""
        decision = TicketAutomationScopeService.evaluate_module(
            {"automationScope": {"enabled": True}},
            module_id=101,
            module_name="库存中心",
        )

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.matched_by, "scope_unrestricted")

    def test_module_code_allows_automation(self):
        """模块 Code 精确匹配时应允许进入自动化范围。"""
        decision = TicketAutomationScopeService.evaluate_module(
            {"automationScope": {"enabled": True, "moduleCodes": ["MOD-POS"]}},
            module_id=101,
            module_name="库存中心",
            module_code="mod-pos",
        )

        self.assertTrue(decision.eligible)
        self.assertEqual(decision.matched_by, "module_code")

    def test_statistics_scope_intersects_user_selected_modules(self):
        """统计默认关注范围应与用户显式选择的模块取交集，避免扩大查询范围。"""
        with (
            patch(
                "modules.ticket.service.stats.ticket_processing_stats_service.TicketSyncConfigService.load_sync_config",
                return_value={"automationScope": {"enabled": True}},
            ),
            patch.object(
                TicketAutomationScopeService,
                "resolve_statistics_scope_module_ids",
                return_value=[10, 20],
            ),
        ):
            result = TicketProcessingStatsService.merge_automation_scope_module_ids(
                SimpleNamespace(),
                [20, 30],
                True,
            )

        self.assertEqual(result, [20])

    def test_statistics_all_data_switch_does_not_apply_scope(self):
        """统计选择全部数据时不得读取或叠加自动化关注范围。"""
        with patch(
            "modules.ticket.service.stats.ticket_processing_stats_service.TicketSyncConfigService.load_sync_config"
        ) as load_config:
            result = TicketProcessingStatsService.merge_automation_scope_module_ids(
                SimpleNamespace(),
                [20, 30],
                False,
            )

        self.assertEqual(result, [20, 30])
        load_config.assert_not_called()

    def test_auto_group_push_is_blocked_before_existing_condition(self):
        """范围外工单必须在原有群推送条件计算前被自动推送门禁拦截。"""
        ticket = SimpleNamespace(
            ticket_id=1,
            ticket_no="INC-SCOPE-1",
            module_id=101,
            module_name="库存中心",
            extra_data={},
        )
        with (
            patch.object(TicketSyncGroupPushService, "resolve_ai_pending_state", return_value=(False, "")),
            patch.object(TicketSyncGroupPushService, "persist_sync_meta", return_value=ticket),
            patch(
                "modules.ticket.service.sync.ticket_sync_group_push_service.TicketSyncConfigService.load_sync_config",
                return_value={
                    "automationScope": {
                        "enabled": True,
                        "moduleNameIncludes": ["POS"],
                    },
                    "groupPush": {"autoPushCondition": "status == '处理中'"},
                },
            ),
            patch(
                "modules.ticket.service.sync.ticket_automation_scope_service.TicketDao.get_module_code_by_id",
                return_value="",
            ),
            patch.object(TicketSyncGroupPushService, "send_auto_group_message_once") as send_auto_group_push,
        ):
            _, _, result = TicketSyncGroupPushService.finalize_publish_state_after_post_process(
                SimpleNamespace(),
                ticket=ticket,
                sync_scene="bitable_pull",
                update_by="test",
            )

        self.assertTrue(result["skipped"])
        self.assertEqual(result["skipReason"], "当前模块未命中自动化关注范围")
        send_auto_group_push.assert_not_called()
