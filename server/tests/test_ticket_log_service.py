import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.ticket.service.log_pull.ticket_log_service import LogService


class TicketLogServiceTests(unittest.TestCase):
    """验证工单日志搜索的文件范围边界。"""

    def test_search_with_file_scope_only_returns_target_file_hits(self):
        """指定日志文件搜索时，不应返回其他文件里的同关键字命中。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            extract_dir = base_dir / "ticket_1" / "extract"
            extract_dir.mkdir(parents=True)
            (extract_dir / "app.log").write_text("keep\nneedle in app\n", encoding="utf-8")
            (extract_dir / "worker.log").write_text("needle in worker\n", encoding="utf-8")

            with patch.object(LogService, "BASE_DIR", base_dir), patch.dict(
                os.environ, {LogService.SEARCH_MODE_ENV: "python"}, clear=False
            ):
                hits = LogService.search(1, "needle", limit=10, with_context=False, file_path="app.log")

        self.assertEqual([item.file for item in hits], ["app.log"])
        self.assertEqual([item.line for item in hits], [2])

    def test_context_rebuilds_stale_encoding_index_for_utf8_log(self):
        """上下文读取遇到缓存编码与 UTF-8 文件不一致时，应重建索引并返回正常中文。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "pos.log"
            log_path.write_text("第一行\n處理成功\n", encoding="utf-8")
            index_meta = LogService._ensure_line_index(log_path)
            index_path = LogService._line_index_path(log_path)
            index_lines = index_path.read_text(encoding="utf-8").splitlines()
            index_meta["encoding"] = "gb18030"
            index_lines[0] = json.dumps(index_meta, ensure_ascii=False)
            index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

            lines = LogService._read_lines_by_index(log_path, 2, 2)
            rebuilt_meta = json.loads(index_path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual([(line_no, content.rstrip("\r\n")) for line_no, content in lines], [(2, "處理成功")])
        self.assertEqual(rebuilt_meta["encoding"], "utf-8")

    def test_detect_file_encoding_accepts_utf8_sample_with_trailing_partial_character(self):
        """UTF-8 样本在中文字符中间截断时，仍应识别为 UTF-8。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "boundary.log"
            log_path.write_bytes(b"a" * 65535 + "中\n".encode())

            encoding = LogService._detect_file_encoding(log_path)

        self.assertEqual(encoding, "utf-8")


if __name__ == "__main__":
    unittest.main()
