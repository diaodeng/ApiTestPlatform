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


if __name__ == "__main__":
    unittest.main()
