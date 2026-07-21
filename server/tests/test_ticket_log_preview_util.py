import unittest

from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogSearchHitModel
from modules.ticket.util.ticket_log_preview_util import build_ticket_log_search_hit_previews


class TicketLogPreviewUtilTests(unittest.TestCase):
    """验证日志搜索结果预览内容的截断边界。"""

    def test_build_search_hit_previews_keeps_first_500_characters(self):
        """超长命中行应只返回行首 500 个字符，并保留完整长度和定位信息。"""
        content = "a" * 600
        hit = TicketLogSearchHitModel(file="pos.log", line=18, content=content)

        preview = build_ticket_log_search_hit_previews([hit])[0]

        self.assertEqual(preview.content, content[:500])
        self.assertEqual(preview.content_length, 600)
        self.assertTrue(preview.content_truncated)
        self.assertEqual((preview.file, preview.line), ("pos.log", 18))
        self.assertEqual(hit.content, content)

    def test_build_search_hit_previews_keeps_short_content(self):
        """未超过预览上限的命中行应原样返回且标记为未截断。"""
        hit = TicketLogSearchHitModel(file="pos.log", line=19, content="正常日志")

        preview = build_ticket_log_search_hit_previews([hit])[0]

        self.assertEqual(preview.content, "正常日志")
        self.assertEqual(preview.content_length, 4)
        self.assertFalse(preview.content_truncated)
