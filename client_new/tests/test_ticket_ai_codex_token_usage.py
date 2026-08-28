import json
import unittest
from pathlib import Path

from services.ticket_ai_analysis_service import TicketAiAnalysisService


class CodexJsonlTokenUsageTests(unittest.TestCase):
    def test_accumulates_all_turns(self):
        """Codex JSONL 事件流中多个 turn.completed 的 usage 应累加为总量，而非取最后一次。"""
        raw_stdout = "\n".join(
            [
                '{"type":"thread.started","session_id":"abc"}',
                '{"type":"turn.started"}',
                '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"好的"}}',
                '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":50,"output_tokens":20}}',
                '{"type":"turn.completed","usage":{"input_tokens":30,"cached_input_tokens":0,"output_tokens":10}}',
            ]
        )

        usage = TicketAiAnalysisService._parse_codex_jsonl_token_usage(raw_stdout)

        self.assertIsNotNone(usage)
        # 累加所有回合：input 100+30=130，output 20+10=30，cached 50
        self.assertEqual(usage["input_tokens"], 130)
        self.assertEqual(usage["output_tokens"], 30)
        self.assertEqual(usage["cached_input_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 160)

    def test_skips_non_json_lines(self):
        """事件流中混入非 JSON 行（进度提示等）时不应中断解析。"""
        raw_stdout = "\n".join(
            [
                "Reading additional input from stdin...",
                '{"type":"turn.completed","usage":{"input_tokens":13273,"cached_input_tokens":2048,"output_tokens":25}}',
                "warning: something else",
            ]
        )

        usage = TicketAiAnalysisService._parse_codex_jsonl_token_usage(raw_stdout)

        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 13273)
        self.assertEqual(usage["output_tokens"], 25)
        self.assertEqual(usage["total_tokens"], 13298)

    def test_returns_none_for_plain_output(self):
        """非事件流输出（如 Claude 的普通 stdout）应返回 None，走原有候选提取逻辑。"""
        self.assertIsNone(TicketAiAnalysisService._parse_codex_jsonl_token_usage("hello world result"))
        self.assertIsNone(TicketAiAnalysisService._parse_codex_jsonl_token_usage(""))
        self.assertIsNone(TicketAiAnalysisService._parse_codex_jsonl_token_usage(None))

    def test_rejects_claude_result_payload(self):
        """Claude 的 type=result 单行 JSON 不应被 Codex 事件流解析误判。"""
        claude_payload = (
            '{"type":"result","is_error":false,"num_turns":4,'
            '"usage":{"input_tokens":27140,"output_tokens":794},"result":"好的"}'
        )

        self.assertIsNone(TicketAiAnalysisService._parse_codex_jsonl_token_usage(claude_payload))

    def test_worker_command_includes_json_flag(self):
        """Codex 命令拼装应包含 --json 以启用 JSONL 事件流。"""
        command = TicketAiAnalysisService._build_worker_command(
            provider_type="codex",
            worker_config=TicketAiAnalysisService._get_provider_worker_config("codex"),
            repo_path=Path("."),
            workspace_dir=Path("."),
            schema_file=None,
            result_file=Path("result.json"),
            selected_worker_model=None,
        )

        self.assertIn("--json", command)


class ClaudeTokenUsageTests(unittest.TestCase):
    def test_accumulates_model_usage_across_models(self):
        """Claude modelUsage 按模型给出累计值，应逐模型累加而非取主模型最后一次。"""
        payload = json.dumps(
            {
                "type": "result",
                "is_error": False,
                "num_turns": 4,
                "usage": {"input_tokens": 27140, "output_tokens": 794},
                "modelUsage": {
                    "claude-opus-4-8[1m]": {
                        "inputTokens": 27140,
                        "outputTokens": 794,
                        "cacheReadInputTokens": 80896,
                        "cacheCreationInputTokens": 0,
                    },
                    "claude-haiku-4-5": {
                        "inputTokens": 786,
                        "outputTokens": 526,
                        "cacheReadInputTokens": 0,
                        "cacheCreationInputTokens": 0,
                    },
                },
                "result": "好的",
            }
        )

        usage = TicketAiAnalysisService._parse_claude_token_usage(payload)

        self.assertIsNotNone(usage)
        # 累加所有模型：input 27140+786，output 794+526，cached 80896
        self.assertEqual(usage["input_tokens"], 27926)
        self.assertEqual(usage["output_tokens"], 1320)
        self.assertEqual(usage["cached_input_tokens"], 80896)
        self.assertEqual(usage["total_tokens"], 29246)

    def test_falls_back_to_top_level_usage_without_model_usage(self):
        """旧版本无 modelUsage 时回退顶层 usage（主模型最后一次调用的近似值）。"""
        payload = json.dumps(
            {
                "type": "result",
                "is_error": False,
                "usage": {"input_tokens": 26814, "output_tokens": 24},
                "result": "好的",
            }
        )

        usage = TicketAiAnalysisService._parse_claude_token_usage(payload)

        self.assertIsNotNone(usage)
        self.assertEqual(usage["input_tokens"], 26814)
        self.assertEqual(usage["output_tokens"], 24)
        self.assertEqual(usage["total_tokens"], 26838)

    def test_rejects_error_and_non_result_payload(self):
        """is_error 或非 result 报文（含 Codex 事件流）不应解析出用量。"""
        error_payload = json.dumps({"type": "result", "is_error": True, "usage": {"input_tokens": 1}})
        self.assertIsNone(TicketAiAnalysisService._parse_claude_token_usage(error_payload))

        codex_last_line = '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":5}}'
        self.assertIsNone(TicketAiAnalysisService._parse_claude_token_usage(codex_last_line))

        self.assertIsNone(TicketAiAnalysisService._parse_claude_token_usage(""))
        self.assertIsNone(TicketAiAnalysisService._parse_claude_token_usage(None))


if __name__ == "__main__":
    unittest.main()
