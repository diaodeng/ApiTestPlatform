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

    def test_accumulate_token_usage_sums_across_calls(self):
        """批次内多次 AI 调用的用量应累加，而不是保留最后一次。"""
        target = {}

        TicketTopicStatsService._accumulate_token_usage(
            target, {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        )
        TicketTopicStatsService._accumulate_token_usage(
            target, {"input_tokens": 50, "output_tokens": 10, "total_tokens": 60}
        )

        self.assertEqual(target, {"input_tokens": 150, "output_tokens": 30, "total_tokens": 180})

    def test_accumulate_token_usage_supports_prompt_keys(self):
        """chat_completions 口径（prompt_tokens 等）也应正确累加。"""
        target = {}

        TicketTopicStatsService._accumulate_token_usage(
            target, {"prompt_tokens": 95, "completion_tokens": 9, "total_tokens": 104}
        )
        TicketTopicStatsService._accumulate_token_usage(
            target, {"prompt_tokens": 88, "completion_tokens": 7, "total_tokens": 95}
        )

        self.assertEqual(target, {"prompt_tokens": 183, "completion_tokens": 16, "total_tokens": 199})

    def test_track_ai_call_counts(self):
        """调用开始/结束计数应正确区分成功与失败。"""
        stats = {}

        TicketTopicStatsService._track_ai_call_start(stats)
        TicketTopicStatsService._track_ai_call_end(stats, success=True)
        TicketTopicStatsService._track_ai_call_start(stats)
        TicketTopicStatsService._track_ai_call_end(stats, success=False)

        self.assertEqual(
            stats,
            {"ai_call_count": 2, "ai_success_count": 1, "ai_failed_count": 1},
        )

    def test_track_ai_call_ignores_none_container(self):
        """未传入统计容器时不应报错。"""
        TicketTopicStatsService._track_ai_call_start(None)
        TicketTopicStatsService._track_ai_call_end(None, success=True)
        TicketTopicStatsService._accumulate_token_usage(None, {"input_tokens": 1})


if __name__ == "__main__":
    unittest.main()
