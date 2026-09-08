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

    @patch("modules.ticket.service.ai.ticket_ai_analysis_service.TicketAiDao.update_task")
    def test_non_success_status_clears_success_fingerprint(self, update_task: Mock):
        """任务失败或重置时必须释放成功指纹，允许同一请求后续重试。"""
        TicketAiAnalysisService._mark_task_status(
            Mock(),
            1003,
            status="failed",
            status_desc="分析失败",
        )

        update_data = update_task.call_args.args[2]
        self.assertIsNone(update_data["success_fingerprint"])

    def test_analysis_result_schema_rejects_wrong_type(self):
        """服务端写回前应拒绝字段类型错误的结构化结果。"""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        }

        self.assertTrue(TicketAiAnalysisService._validate_analysis_result_schema({"ticket_id": 1001}, schema))
        self.assertFalse(TicketAiAnalysisService._validate_analysis_result_schema({"ticket_id": "1001"}, schema))


if __name__ == "__main__":
    unittest.main()


class RawOutputTruncateTests(unittest.TestCase):
    """Agent 响应 raw_output 兜底截断的回归测试。"""

    def test_truncate_dict_response_raw_output(self):
        """dict 形态响应的超长 raw_output 应被就地截断。"""
        response = {"result": {"analysis_result": {"root_cause": "x"}, "raw_output": "A" * 90000}}
        TicketAiAnalysisService._truncate_response_raw_output(response)
        result = response["result"]
        self.assertEqual(len(result["raw_output"]), TicketAiAnalysisService.RESPONSE_RAW_OUTPUT_MAX_CHARS)
        self.assertEqual(result["analysis_result"], {"root_cause": "x"})

    def test_truncate_model_response_raw_output(self):
        """pydantic 模型形态响应的超长 raw_output 应被就地截断。"""
        response = Mock()
        response.result = {"raw_output": "B" * 90000}
        TicketAiAnalysisService._truncate_response_raw_output(response)
        self.assertEqual(len(response.result["raw_output"]), TicketAiAnalysisService.RESPONSE_RAW_OUTPUT_MAX_CHARS)

    def test_truncate_keeps_short_raw_output(self):
        """未超长的 raw_output 保持原样。"""
        response = {"result": {"raw_output": "short output"}}
        TicketAiAnalysisService._truncate_response_raw_output(response)
        self.assertEqual(response["result"]["raw_output"], "short output")

    def test_truncate_tolerates_missing_or_invalid_fields(self):
        """缺 result / 非法字段时不抛异常。"""
        for response in (None, {}, {"result": None}, {"result": {"raw_output": None}}, {"other": 1}):
            TicketAiAnalysisService._truncate_response_raw_output(response)
