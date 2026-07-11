import unittest
from datetime import datetime

from modules.ticket.util.ticket_statistics_time_util import TicketStatisticsTimeUtil


class TicketStatisticsTimeUtilTests(unittest.TestCase):
    """验证工单统计默认时间和业务周边界。"""

    def _config(self, **overrides):
        """构造业务周测试配置。"""
        config = dict(TicketStatisticsTimeUtil.DEFAULT_CONFIG)
        config.update(overrides)
        return TicketStatisticsTimeUtil.normalize_config(config)

    def test_business_week_before_thursday_18_belongs_to_previous_week(self):
        """周四 18:00 前仍属于上一业务周。"""
        config = self._config()
        current = datetime(2026, 7, 9, 17, 59, 0)

        start = TicketStatisticsTimeUtil.business_week_start_for_time(current, config)

        self.assertEqual(start, datetime(2026, 7, 2, 18, 0, 0))

    def test_business_week_after_thursday_18_starts_current_day(self):
        """周四 18:00 后归属新的业务周。"""
        config = self._config()
        current = datetime(2026, 7, 9, 18, 1, 0)

        start = TicketStatisticsTimeUtil.business_week_start_for_time(current, config)

        self.assertEqual(start, datetime(2026, 7, 9, 18, 0, 0))

    def test_current_business_week_default_range(self):
        """current 模式返回当前业务周日期范围。"""
        config = self._config(businessWeekDefaultWindow="current")
        current = datetime(2026, 7, 9, 18, 1, 0)

        result = TicketStatisticsTimeUtil.get_default_range(config, now=current)

        self.assertEqual(
            result,
            {"beginTime": "2026-07-09 18:00:00", "endTime": "2026-07-16 17:59:59"},
        )

    def test_previous_completed_business_week_default_range(self):
        """previous_completed 模式返回上一完整业务周日期范围。"""
        config = self._config(businessWeekDefaultWindow="previous_completed")
        current = datetime(2026, 7, 9, 18, 1, 0)

        result = TicketStatisticsTimeUtil.get_default_range(config, now=current)

        self.assertEqual(
            result,
            {"beginTime": "2026-07-02 18:00:00", "endTime": "2026-07-09 17:59:59"},
        )

    def test_rolling_days_default_range_and_label(self):
        """rolling_days 模式显示最近 N 天，不写成最近一周。"""
        config = self._config(defaultRangeMode="rolling_days", rollingDays=7)
        current = datetime(2026, 7, 11, 10, 0, 0)

        result = TicketStatisticsTimeUtil.get_default_range(config, now=current)
        label = TicketStatisticsTimeUtil.get_range_label(config, result)

        self.assertEqual(
            result,
            {"beginTime": "2026-07-05 00:00:00", "endTime": "2026-07-11 23:59:59"},
        )
        self.assertIn("最近 7 天", label)
        self.assertNotIn("最近一周", label)


if __name__ == "__main__":
    unittest.main()
