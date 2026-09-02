"""
失败/超时/缓存路径 Token 用量提取测试。

覆盖：
- 失败路径从 Codex JSONL 已完成 turn 中提取真实消耗；
- 失败路径从结果文件内嵌 usage 提取；
- 缓存命中从结果 payload 或落盘 stdout 恢复 token；
- 无任何凭据时返回 None（服务端记 unknown，不记 0）。
"""

import json
import tempfile
import unittest
from pathlib import Path

from services.ticket_ai_analysis_service import TicketAiAnalysisService


class FailureTokenUsageTests(unittest.TestCase):
    def test_codex_failure_extracts_completed_turn_usage(self):
        """Worker 失败但 JSONL 已有 turn.completed 时，应提取出真实消耗。"""
        raw_stdout = "\n".join(
            [
                '{"type":"thread.started","session_id":"abc"}',
                '{"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":20,"output_tokens":15}}',
            ]
        )

        usage = TicketAiAnalysisService._parse_failure_token_usage(
            provider_type="codex",
            raw_stdout=raw_stdout,
            raw_stderr="codex exited with code 1",
        )

        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 120)
        self.assertEqual(usage["output_tokens"], 15)
        self.assertEqual(usage["total_tokens"], 135)

    def test_claude_failure_extracts_model_usage(self):
        """Claude 失败输出含 modelUsage 时应提取累计消耗。"""
        raw_stdout = json.dumps(
            {
                "type": "result",
                "is_error": True,
                "modelUsage": {
                    "claude-sonnet": {"inputTokens": 200, "outputTokens": 30, "cacheReadInputTokens": 10}
                },
            }
        )

        usage = TicketAiAnalysisService._parse_failure_token_usage(
            provider_type="claude",
            raw_stdout=raw_stdout,
            raw_stderr=None,
        )

        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 200)
        self.assertEqual(usage["output_tokens"], 30)

    def test_failure_with_no_evidence_returns_none(self):
        """失败且无任何 usage 凭据时应返回 None（不伪造 0）。"""
        usage = TicketAiAnalysisService._parse_failure_token_usage(
            provider_type="codex",
            raw_stdout="",
            raw_stderr="process killed",
        )
        self.assertIsNone(usage)

    def test_failure_extracts_usage_from_result_file(self):
        """结果文件内嵌 usage 时应通过通用候选提取。"""
        with tempfile.TemporaryDirectory() as tmp:
            result_file = Path(tmp) / "result.json"
            result_file.write_text(
                json.dumps({"token_usage": {"input_tokens": 55, "output_tokens": 6}}),
                encoding="utf-8",
            )
            usage = TicketAiAnalysisService._parse_failure_token_usage(
                provider_type="codex",
                raw_stdout="",
                raw_stderr=None,
                result_file=result_file,
            )
            self.assertIsNotNone(usage)
            self.assertEqual(usage["input_tokens"], 55)
            self.assertEqual(usage["output_tokens"], 6)


class WorkspaceTokenRecoveryTests(unittest.TestCase):
    def test_recover_from_workspace_stream_files(self):
        """超时/异常分支应能从工作区落盘的 stdout 流文件恢复 token。"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "worker.stdout.txt").write_text(
                '{"type":"turn.completed","usage":{"input_tokens":80,"cached_input_tokens":0,"output_tokens":9}}',
                encoding="utf-8",
            )
            usage = TicketAiAnalysisService._recover_token_usage_from_workspace(
                workspace, provider_type="codex"
            )
            self.assertIsNotNone(usage)
            self.assertEqual(usage["input_tokens"], 80)
            self.assertEqual(usage["output_tokens"], 9)

    def test_recover_missing_workspace_returns_none(self):
        """工作区不存在时返回 None。"""
        usage = TicketAiAnalysisService._recover_token_usage_from_workspace(
            None, provider_type="codex"
        )
        self.assertIsNone(usage)


class CachedResultTokenTests(unittest.TestCase):
    def test_extract_usage_from_cached_result_payload(self):
        """缓存命中时结果 payload 内嵌 usage 应被提取。"""
        cached = {"analysis_summary": "ok", "token_usage": {"input_tokens": 10, "output_tokens": 5}}
        usage = TicketAiAnalysisService._extract_token_usage_payload(cached)
        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 10)


if __name__ == "__main__":
    unittest.main()
