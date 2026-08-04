"""工单自定义实时统计方案与聚合测试。"""
import unittest
from datetime import datetime
from types import SimpleNamespace

from modules.ticket.service.stats.ticket_custom_statistics_definition_service import (
    TicketCustomStatisticsDefinitionService,
)
from modules.ticket.service.stats.ticket_custom_statistics_service import TicketCustomStatisticsService


class TicketCustomStatisticsServiceTests(unittest.TestCase):
    """验证统计方案白名单、结论规则和实时内存聚合。"""

    def test_profile_normalization_rejects_unknown_condition_field(self):
        """配置不能把未注册字段或任意表达式带入统计执行链路。"""
        profiles = TicketCustomStatisticsDefinitionService.normalize_profiles(
            [
                {
                    "profileCode": "daily_conclusion",
                    "label": "每日结论",
                    "grouping": {
                        "mode": "rules",
                        "groups": [
                            {
                                "groupCode": "unsafe",
                                "conditions": [
                                    {"sourceField": "__import__", "operator": "equals", "matchValues": ["x"]}
                                ],
                            }
                        ],
                    },
                }
            ]
        )

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["grouping"]["groups"], [])
        self.assertEqual(profiles[0]["timeField"], "submitTime")

    def test_rule_grouping_uses_processed_time_for_conclusion(self):
        """是否有结论可由 processed_at 派生字段配置，而不是绑定固定状态。"""
        profile = TicketCustomStatisticsDefinitionService.normalize_profiles(
            [
                {
                    "profileCode": "coupon_conclusion",
                    "label": "券模块结论",
                    "grouping": {
                        "mode": "rules",
                        "overlapMode": "exclusive",
                        "includeUnmatched": True,
                        "groups": [
                            {
                                "groupCode": "has_conclusion",
                                "label": "有结论",
                                "priority": 100,
                                "conditions": [
                                    {"sourceField": "hasConclusion", "operator": "equals", "matchValues": ["true"]}
                                ],
                            },
                            {
                                "groupCode": "no_conclusion",
                                "label": "无结论",
                                "priority": 90,
                                "conditions": [
                                    {"sourceField": "hasConclusion", "operator": "equals", "matchValues": ["false"]}
                                ],
                            },
                        ],
                    },
                    "notification": {"includeTopTickets": True, "topTicketLimit": 2},
                }
            ]
        )[0]
        tickets = [
            self.make_ticket("INC-1", processed_at=datetime(2026, 8, 4, 9, 0)),
            self.make_ticket("INC-2", processed_at=None),
        ]

        result = TicketCustomStatisticsService.aggregate_tickets(
            profile=profile,
            tickets=tickets,
            start_time=datetime(2026, 8, 4, 0, 0),
            end_time=datetime(2026, 8, 4, 10, 0),
        )

        self.assertEqual(result.total_count, 2)
        self.assertEqual({item.label: item.count for item in result.groups}, {"有结论": 1, "无结论": 1})
        self.assertEqual([item.ticket_no for item in result.top_tickets], ["INC-1", "INC-2"])

    def test_custom_time_range_requires_valid_left_closed_right_open_bounds(self):
        """固定范围应保留配置时间，并拒绝结束时间不晚于开始时间的配置。"""
        start_time, end_time = TicketCustomStatisticsService.resolve_time_range(
            {"mode": "custom", "startTime": "2026-08-01T00:00:00", "endTime": "2026-08-02T00:00:00"},
            start_time=None,
            end_time=None,
        )

        self.assertEqual(start_time, datetime(2026, 8, 1, 0, 0))
        self.assertEqual(end_time, datetime(2026, 8, 2, 0, 0))
        with self.assertRaisesRegex(ValueError, "自定义时间范围"):
            TicketCustomStatisticsService.resolve_time_range(
                {"mode": "custom", "startTime": "2026-08-02T00:00:00", "endTime": "2026-08-02T00:00:00"},
                start_time=None,
                end_time=None,
            )

    def test_notification_uses_common_feishu_auth_when_profile_does_not_override(self):
        """方案可复用统一飞书凭证，同时允许单方案显式覆盖。"""
        notification = TicketCustomStatisticsService.resolve_notification_config(
            {"enabled": True, "appId": "", "appSecret": "profile-secret"},
            {"appId": "common-app", "appSecret": "common-secret"},
        )

        self.assertEqual(notification["appId"], "common-app")
        self.assertEqual(notification["appSecret"], "profile-secret")

    @staticmethod
    def make_ticket(ticket_no: str, processed_at: datetime | None):
        """构造仅含统计白名单字段的工单测试对象。"""
        return SimpleNamespace(
            ticket_no=ticket_no,
            title=f"标题 {ticket_no}",
            ticket_url="",
            issue_type_id="support_consulting",
            is_problem=False,
            status="PROCESSING",
            source="manual",
            root_cause_type="",
            solution_type="",
            resolution_code="",
            internal_priority="P2",
            project_id=1,
            module_id=2,
            module_name="券",
            problem_pattern_code="",
            processed_at=processed_at,
        )


if __name__ == "__main__":
    unittest.main()
