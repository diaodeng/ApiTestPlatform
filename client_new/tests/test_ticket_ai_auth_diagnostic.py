from __future__ import annotations

import asyncio
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ticket_ai_analysis_service import TicketAiAnalysisService


class _FakeHttpResponse:
    """模拟鉴权探测的 HTTP 响应。"""

    status_code = 401
    headers = {"x-request-id": "request-id-for-test"}


class _FakeAsyncClient:
    """模拟 httpx.AsyncClient，避免单元测试访问真实 Provider。"""

    last_url = ""
    last_headers: dict[str, str] = {}

    def __init__(self, **_: object) -> None:
        """接收 AsyncClient 初始化参数。"""

    async def __aenter__(self) -> "_FakeAsyncClient":
        """进入异步上下文并返回当前客户端。"""
        return self

    async def __aexit__(self, *_: object) -> None:
        """退出异步上下文。"""

    async def get(self, url: str, *, headers: dict[str, str]) -> _FakeHttpResponse:
        """记录探测请求并返回预设的未授权响应。"""
        type(self).last_url = url
        type(self).last_headers = headers
        return _FakeHttpResponse()


class TicketAiAuthDiagnosticTests(unittest.TestCase):
    """验证 Codex Worker 鉴权故障诊断不会泄漏密钥。"""

    def test_build_worker_auth_diagnostic_prefers_task_auth_json(self) -> None:
        """任务级 auth.json 存在时，应优先作为 Codex 实际认证来源。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ai_home = Path(temp_dir)
            (ai_home / "config.toml").write_text(
                'base_url = "https://provider.example/v1"\n',
                encoding="utf-8",
            )
            (ai_home / "auth.json").write_text(
                json.dumps({"OPENAI_API_KEY": "auth-json-key"}),
                encoding="utf-8",
            )

            diagnostic, api_key = TicketAiAnalysisService._build_worker_auth_diagnostic(
                provider_type="codex",
                provider_code="provider-code",
                worker_model="gpt-test",
                ai_home=ai_home,
                env_values={"OPENAI_API_KEY": "environment-key", "OPENAI_BASE_URL": "https://env.example/v1"},
            )

            self.assertEqual(api_key, "auth-json-key")
            self.assertEqual(diagnostic["api_key_source"], "auth.json.OPENAI_API_KEY")
            self.assertEqual(diagnostic["base_url"], "https://provider.example/v1")
            self.assertTrue(diagnostic["api_key_present"])
            self.assertEqual(diagnostic["api_key_length"], len("auth-json-key"))
            self.assertNotIn("auth-json-key", json.dumps(diagnostic))

    def test_build_worker_auth_diagnostic_prefers_config_bearer_token(self) -> None:
        """Codex 配置存在 bearer token 时，诊断应以 CLI 实际使用的令牌为准。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ai_home = Path(temp_dir)
            (ai_home / "config.toml").write_text(
                '[model_providers.custom]\nexperimental_bearer_token = "config-token"\n'
                'base_url = "https://provider.example/v1"\n',
                encoding="utf-8",
            )
            (ai_home / "auth.json").write_text(
                json.dumps({"OPENAI_API_KEY": "auth-json-key"}),
                encoding="utf-8",
            )

            diagnostic, api_key = TicketAiAnalysisService._build_worker_auth_diagnostic(
                provider_type="codex",
                provider_code="provider-code",
                worker_model="gpt-test",
                ai_home=ai_home,
                env_values={"OPENAI_API_KEY": "environment-key"},
            )

            self.assertEqual(api_key, "config-token")
            self.assertEqual(diagnostic["api_key_source"], "config.toml.experimental_bearer_token")
            self.assertEqual(diagnostic["api_key_length"], len("config-token"))
            self.assertNotIn("config-token", json.dumps(diagnostic))

    def test_patch_codex_config_updates_experimental_bearer_token(self) -> None:
        """Provider 密钥下发时，应覆盖复制来的旧 Codex bearer token。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "config.toml").write_text(
                'model_provider = "custom"\n\n'
                '[model_providers.custom]\n'
                'base_url = "https://old.example/v1"\n'
                'experimental_bearer_token = "PROXY_MANAGED"\n\n'
                '[notice]\nvalue = true\n',
                encoding="utf-8",
            )

            TicketAiAnalysisService._patch_codex_config_for_provider(
                codex_home,
                {"OPENAI_BASE_URL": "https://provider.example/v1", "OPENAI_API_KEY": "provider-key"},
            )

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('base_url = "https://provider.example/v1"', config_text)
            self.assertIn('experimental_bearer_token = "provider-key"', config_text)
            self.assertNotIn('experimental_bearer_token = "PROXY_MANAGED"', config_text)

    def test_is_unauthorized_worker_failure_matches_expected_errors(self) -> None:
        """401、Unauthorized 和 Invalid token 都应触发轻量鉴权探测。"""
        self.assertTrue(TicketAiAnalysisService._is_unauthorized_worker_failure("", "ERROR: 401 Unauthorized"))
        self.assertTrue(TicketAiAnalysisService._is_unauthorized_worker_failure("Invalid token", ""))
        self.assertFalse(TicketAiAnalysisService._is_unauthorized_worker_failure("", "ERROR: timeout"))

    def test_probe_codex_authentication_returns_status_without_recording_key(self) -> None:
        """探测应只返回 HTTP 状态和请求 ID，并按 Bearer 方式发送密钥。"""
        with patch("services.ticket_ai_analysis_service.httpx.AsyncClient", _FakeAsyncClient):
            result = asyncio.run(
                TicketAiAnalysisService._probe_codex_authentication(
                    "https://provider.example/v1/",
                    "diagnostic-test-key",
                )
            )

        self.assertEqual(result["auth_probe"], "completed")
        self.assertEqual(result["auth_probe_http_status"], 401)
        self.assertEqual(result["auth_probe_request_id"], "request-id-for-test")
        self.assertEqual(_FakeAsyncClient.last_url, "https://provider.example/v1/models")
        self.assertEqual(_FakeAsyncClient.last_headers["Authorization"], "Bearer diagnostic-test-key")
        self.assertNotIn("diagnostic-test-key", json.dumps(result))

    def test_patch_codex_config_updates_indented_model_provider_base_url(self) -> None:
        """Provider 下发的地址应覆盖 Codex 模型 Provider 节中的缩进配置。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            config_file = codex_home / "config.toml"
            config_file.write_text(
                '[model_providers.custom]\n'
                '  name = "custom"\n'
                '  base_url = "https://old.example/v1"\n',
                encoding="utf-8",
            )

            TicketAiAnalysisService._patch_codex_config_for_provider(
                codex_home,
                {"OPENAI_BASE_URL": "https://new.example/v1"},
            )

            config_text = config_file.read_text(encoding="utf-8")
            self.assertIn('base_url = "https://new.example/v1"', config_text)
            self.assertNotIn("old.example", config_text)

    def test_prepare_claude_env_overwrites_previous_provider_values(self) -> None:
        """Claude 工作区重试时应覆盖旧 Provider 的地址和密钥。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_dir = Path(temp_dir)
            env_file = workspace_dir / ".env"
            env_file.write_text(
                "ANTHROPIC_API_KEY=old-key\n"
                "ANTHROPIC_BASE_URL=https://old.example\n"
                "OTHER=value\n",
                encoding="utf-8",
            )

            TicketAiAnalysisService._prepare_claude_env(
                workspace_dir,
                {
                    "ANTHROPIC_API_KEY": "new-key",
                    "ANTHROPIC_BASE_URL": "https://new.example",
                },
            )

            env_text = env_file.read_text(encoding="utf-8")
            self.assertIn("ANTHROPIC_API_KEY=new-key", env_text)
            self.assertIn("ANTHROPIC_BASE_URL=https://new.example", env_text)
            self.assertNotIn("old-key", env_text)
            self.assertNotIn("old.example", env_text)
            self.assertIn("OTHER=value", env_text)

    def test_codex_result_ignores_stderr_when_json_matches_schema(self) -> None:
        """Codex 退出成功且结果通过 schema 时，即使 stderr 有正常进度也应返回成功结果。"""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            result_file = Path(temp_dir) / "result.json"
            result_file.write_text('```json\n{"ticket_id": 1001}\n```', encoding="utf-8")

            result = TicketAiAnalysisService._parse_worker_output(
                provider_type="codex",
                worker_config={"output_mode": "file"},
                result_file=result_file,
                raw_stdout="",
                raw_stderr="正常进度输出，不是错误",
                schema_payload=schema,
            )

        self.assertEqual(result, {"ticket_id": 1001})

    def test_cached_result_returns_success_without_worker_execution(self) -> None:
        """重试命中有效 result.json 时应直接成功返回，不因缓存分支字段未初始化而失败。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            task_workspace = workspace_root / "ticket_1001" / "task_2001"
            task_workspace.mkdir(parents=True)
            cached_result = {"root_cause": "cached-result"}
            (task_workspace / "result.json").write_text(
                json.dumps(cached_result, ensure_ascii=False),
                encoding="utf-8",
            )
            request = {
                "taskId": 2001,
                "ticketId": 1001,
                "ticket": {},
                "mapping": {},
                "context": {},
                "timeline": {},
                "resultSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"root_cause": {"type": "string"}},
                    "required": ["root_cause"],
                },
            }

            async def fake_emit_event(*_: object, **__: object) -> None:
                """缓存命中测试不需要向服务端发送事件。"""

            with patch.object(
                TicketAiAnalysisService,
                "_resolve_ai_repo_runtime_settings",
                return_value=(workspace_root, workspace_root, "main"),
            ), patch.object(TicketAiAnalysisService, "_emit_event", new=fake_emit_event):
                result = asyncio.run(TicketAiAnalysisService.handle_request(request))

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["analysis_result"], cached_result)
        self.assertIsNone(result["result"]["token_usage"])

    def test_worker_result_rejects_invalid_schema(self) -> None:
        """结果 JSON 可解析但不满足 schema 时，不应被当作成功结果。"""
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"ticket_id": {"type": "integer"}},
            "required": ["ticket_id"],
        }
        result = TicketAiAnalysisService._parse_worker_output(
            provider_type="codex",
            worker_config={"output_mode": "stdout"},
            result_file=None,
            raw_stdout='{"ticket_id": "1001"}',
            raw_stderr="",
            schema_payload=schema,
        )

        self.assertIsNone(result)

    def test_codex_trusts_only_current_workspace(self) -> None:
        """任务级 Codex 配置只能加入当前工作区，不应扩大到仓库父目录。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            workspace = root / "ticket_1001" / "task_2001"
            workspace.mkdir(parents=True)

            TicketAiAnalysisService._trust_codex_workspace(codex_home, workspace)

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            tomllib.loads(config_text)
            self.assertIn(f"[projects.'{workspace.resolve()}']", config_text)
            self.assertIn('trust_level = "trusted"', config_text)
            self.assertNotIn(f"[projects.'{root.resolve()}']", config_text)

    def test_codex_rewrites_existing_windows_workspace_trust_without_escape_error(self) -> None:
        """重试更新已有 Windows 工作区 trusted 段落时，不应触发反斜杠替换错误。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            workspace = root / "ticket_1001" / "task_2001"
            workspace.mkdir(parents=True)

            TicketAiAnalysisService._trust_codex_workspace(codex_home, workspace)
            TicketAiAnalysisService._trust_codex_workspace(codex_home, workspace)

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(config_text.count(f"[projects.'{workspace.resolve()}']"), 1)
            self.assertIn('trust_level = "trusted"', config_text)

    def test_codex_command_uses_workspace_and_controlled_worktree_permissions(self) -> None:
        """Codex 应以任务工作区为主目录，并只额外放行指定 worktree。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "ticket_1001" / "task_2001"
            repo = root / "repo_worktrees" / "branch"
            workspace.mkdir(parents=True)
            repo.mkdir(parents=True)
            with patch.object(
                TicketAiAnalysisService,
                "_resolve_provider_executable",
                return_value=["codex", "exec"],
            ):
                command = TicketAiAnalysisService._build_worker_command(
                    provider_type="codex",
                    worker_config=TicketAiAnalysisService.PROVIDER_WORKER_MAP["codex"],
                    repo_path=repo,
                    workspace_dir=workspace,
                    schema_file=None,
                    result_file=None,
                    selected_worker_model=None,
                )

        self.assertEqual(command[command.index("-C") + 1], str(workspace))
        self.assertEqual(command[command.index("--add-dir") + 1], str(repo))
        self.assertIn("--approve-for-me", command)
        self.assertNotIn("-s", command)


if __name__ == "__main__":
    unittest.main()
