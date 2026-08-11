import unittest

from modules.ticket.service.stats.ticket_topic_stats_service import TicketTopicStatsService


class TicketTopicStatsServiceTests(unittest.TestCase):
    """验证专题工单统计的主题提取和分类边界。"""

    def test_full_width_topic_colon_extracts_topic(self):
        """中文全角冒号的主题行也应被正确提取。"""
        content = "Ticket：INC00001660915\n主题：OPEN TICKET - Z read differs from EOD Consolidated Report\n商家：SG-7E"

        topic = TicketTopicStatsService.extract_topic(content)

        self.assertEqual(topic, "OPEN TICKET - Z read differs from EOD Consolidated Report")

    def test_bi_report_ticket_does_not_match_coupon_category(self):
        """BI 报表类工单没有券关键词时，不应因为整条消息内容误归类为券。"""
        content = """Ticket：INC00001660915
主题：OPEN TICKET - Z read differs from EOD Consolidated Report
商家：SG-7E
门店：3868
一线：@Eddie Chan
当前处理人：@熊杰
详情：“RTA工单处理清单明细”的记录
当前记录已开启高级权限

熊杰
15:12
@徐小惠 帮忙看下这个工单
徐小惠
16:10
@熊杰 这个看着像BI报表，转何俊那边看看了"""

        topic = TicketTopicStatsService.extract_topic(content)
        category = TicketTopicStatsService.get_category_bucket(topic)

        self.assertEqual(topic, "OPEN TICKET - Z read differs from EOD Consolidated Report")
        self.assertEqual(category, "其他")

    def test_topic_coupon_keyword_still_matches_coupon_category(self):
        """主题本身包含券关键词时，仍应归类为券。"""
        topic = "OPEN TICKET - coupon: cannot be applied"

        category = TicketTopicStatsService.get_category_bucket(topic)

        self.assertEqual(category, "券")

    def test_english_keyword_inside_word_does_not_match_category(self):
        """英文关键词出现在其他单词内部时，不应作为专题关键词命中。"""
        topic = "OPEN TICKET - backupcouponvalue differs from report"

        category = TicketTopicStatsService.get_category_bucket(topic)

        self.assertEqual(category, "其他")

    def test_extra_coupon_keywords_are_merged_with_defaults(self):
        """任务参数补充关键词后，应与代码内置关键词合并而不是替换。"""
        topic = "OPEN TICKET - reward voucher cannot be applied"

        category = TicketTopicStatsService.get_category_bucket(topic, coupon_keywords=["reward voucher"])

        self.assertEqual(category, "券")

    def test_extra_status_keywords_are_merged_with_defaults(self):
        """任务参数补充状态关键词后，应与代码内置关键词合并而不是替换。"""
        content = "Ticket：INC00001660915\n主题：OPEN TICKET - reward issue"
        replies = [{"content": "这是 reward resolved 的结果"}]

        status = TicketTopicStatsService.get_session_status(
            content,
            replies,
            conclusion_keywords=["reward resolved"],
        )

        self.assertEqual(status, "有结论")


if __name__ == "__main__":
    unittest.main()
