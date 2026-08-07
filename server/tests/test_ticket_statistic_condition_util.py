"""工单自定义趋势条件运算符测试。"""
import unittest

from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.util.ticket_statistic_condition_util import match_value


class TicketStatisticConditionUtilTests(unittest.TestCase):
    """验证空值条件的运行时匹配和配置归一化行为。"""

    def test_empty_operators_match_none_blank_and_non_blank_values(self):
        """为空应匹配 None、空字符串和空白；不为空只匹配实际内容。"""
        for value in (None, "", "  "):
            self.assertTrue(match_value(value, "is_empty", []))
            self.assertFalse(match_value(value, "is_not_empty", []))
        self.assertFalse(match_value("system_bug", "is_empty", []))
        self.assertTrue(match_value("system_bug", "is_not_empty", []))

    def test_empty_operator_normalization_does_not_require_match_values(self):
        """保存自定义趋势指标时为空条件必须保留空匹配值。"""
        metrics = TicketSyncConfigService.normalize_custom_trend_metrics(
            [
                {
                    "metricCode": "uncategorized",
                    "label": "未分类趋势",
                    "groups": [
                        {
                            "groupCode": "empty_issue_type",
                            "conditions": [
                                {
                                    "sourceField": "issueTypeId",
                                    "operator": "is_empty",
                                    "matchValues": [],
                                }
                            ],
                        }
                    ],
                }
            ]
        )

        condition = metrics[0]["groups"][0]["conditions"][0]
        self.assertEqual(condition["operator"], "is_empty")
        self.assertEqual(condition["matchValues"], [])
