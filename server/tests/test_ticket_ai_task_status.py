import unittest
from unittest.mock import Mock, patch

from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class TicketAiTaskStatusTests(unittest.TestCase):
    """验证工单 AI 任务状态更新不会向非空命令字段写入 NULL。"""

    @patch("modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task")
    def test_missing_command_line_is_normalized_to_empty_string(self, update_task: Mock):
        """未提供执行命令时，应将 command_line 规范化为空字符串。"""
        TicketAiAnalysisService._mark_task_status(
            Mock(),
            1001,
            status="failed",
            status_desc="服务重启前任务未完成，已清理为失败",
            command_line=None,
        )

        update_data = update_task.call_args.args[2]
        self.assertEqual(update_data["command_line"], "")

    @patch("modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task")
    def test_command_line_is_preserved_when_provided(self, update_task: Mock):
        """已提供执行命令时，应保留原始命令内容。"""
        TicketAiAnalysisService._mark_task_status(
            Mock(),
            1002,
            status="failed",
            status_desc="分析失败",
            command_line="agent:codex",
        )

        update_data = update_task.call_args.args[2]
        self.assertEqual(update_data["command_line"], "agent:codex")


if __name__ == "__main__":
    unittest.main()
