import unittest

from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogSearchHitModel
from modules.ticket.util.ticket_log_preview_util import build_ticket_log_search_hit_previews


class TicketLogPreviewUtilTests(unittest.TestCase):
    """验证兼容预览函数不再执行固定字符截断。"""

    def test_build_search_hit_previews_passes_through_long_content(self):
        """已按搜索配置处理的超长命中行应保持原内容和截断标记。"""
        content = "a" * 600
        hit = TicketLogSearchHitModel(
            file="pos.log", line=18, content=content, content_length=120, content_truncated=True
        )
        hits = [hit]

        result = build_ticket_log_search_hit_previews(hits)

        self.assertIs(result, hits)
        self.assertIs(result[0], hit)
        self.assertEqual(result[0].content, content)
        self.assertEqual(result[0].content_length, 120)
        self.assertTrue(result[0].content_truncated)

    def test_build_search_hit_previews_passes_through_short_content(self):
        """短内容也应直接透传，不生成额外对象。"""
        hit = TicketLogSearchHitModel(file="pos.log", line=19, content="正常日志")
        hits = [hit]

        result = build_ticket_log_search_hit_previews(hits)

        self.assertIs(result, hits)
        self.assertIs(result[0], hit)
        self.assertEqual(result[0].content, "正常日志")


if __name__ == "__main__":
    unittest.main()
