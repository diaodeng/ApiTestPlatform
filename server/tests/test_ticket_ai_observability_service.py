import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ai.ticket_ai_observability_service import TicketAiObservabilityService
from utils.api_key_util import ApiKeyUtil


def build_provider(**overrides):
    """构造带可观测字段的 Provider 测试对象。"""
    fields = {
        "observability_enabled": True,
        "observability_endpoint": "https://observe.example/observe",
        "observability_auth_type": "bearer",
        "observability_api_key_cipher_text": ApiKeyUtil.encrypt_api_key("obs-key-123"),
        "observability_service_name": "",
        "observability_cli_enabled": False,
        "provider_code": "obs-provider",
        "platform_code": "custom",
        "api_key_cipher_text": ApiKeyUtil.encrypt_api_key("provider-key"),
        "api_protocol": "openai_chat_completions",
        "base_url": "",
        "default_model": "",
        "provider_name": "Provider",
        "provider_level": 1,
        "worker_env": {},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def build_obs_config(**overrides):
    """构造可观测上报配置。"""
    config = {
        "endpoint": "https://observe.example/observe",
        "auth_header": "Bearer obs-key-123",
        "service_name": "ticket-ai-analysis",
        "provider_code": "obs-provider",
        "platform_code": "custom",
    }
    config.update(overrides)
    return config


class TicketAiObservabilityServiceTests(unittest.TestCase):
    """验证工单 AI 可观测配置解析与 Agent 环境注入分层。"""

    def test_build_provider_config_bearer(self) -> None:
        """bearer 模式应解密密钥并生成 Bearer 头与默认 service name。"""
        config = TicketAiObservabilityService.build_provider_config(build_provider())
        self.assertEqual(config["endpoint"], "https://observe.example/observe")
        self.assertEqual(config["auth_header"], "Bearer obs-key-123")
        self.assertEqual(config["service_name"], "ticket-ai-analysis")

    def test_build_provider_config_basic(self) -> None:
        """basic 模式应把 publicKey:secretKey 合并串编码为 Basic 凭据。"""
        import base64

        provider = build_provider(
            observability_auth_type="basic",
            observability_api_key_cipher_text=ApiKeyUtil.encrypt_api_key("pk-1:sk-2"),
        )
        config = TicketAiObservabilityService.build_provider_config(provider)
        expected = base64.b64encode(b"pk-1:sk-2").decode("ascii")
        self.assertEqual(config["auth_header"], f"Basic {expected}")

    def test_build_provider_config_disabled_or_incomplete(self) -> None:
        """未启用或缺少端点/密文时应返回 None。"""
        self.assertIsNone(TicketAiObservabilityService.build_provider_config(None))
        self.assertIsNone(TicketAiObservabilityService.build_provider_config(build_provider(observability_enabled=False)))
        self.assertIsNone(TicketAiObservabilityService.build_provider_config(build_provider(observability_endpoint="")))
        with patch(
            "modules.ticket.service.ai.ticket_ai_observability_service.ApiKeyUtil.decrypt_api_key",
            side_effect=ValueError("decrypt failed"),
        ):
            self.assertIsNone(TicketAiObservabilityService.build_provider_config(build_provider()))

    def test_env_base_otel_injected_when_enabled_without_cli(self) -> None:
        """主开关开启（CLI 关闭）应下发基础 OTLP + session/trace，供 Agent 任务span上报。"""
        result = TicketAiAnalysisService._build_provider_env_overrides(
            build_provider(observability_cli_enabled=False),
            observability_config=build_obs_config(),
            session_id="ticket-ai-task-1001",
            observability_trace={"trace_id": "a" * 32, "span_id": "b" * 16},
        )
        self.assertEqual(result["OTEL_EXPORTER_OTLP_ENDPOINT"], "https://observe.example/observe")
        self.assertEqual(result["OTEL_EXPORTER_OTLP_HEADERS"], "Authorization=Bearer obs-key-123")
        self.assertEqual(result["OTEL_SESSION_ID"], "ticket-ai-task-1001")
        self.assertEqual(result["OTEL_TRACE_ID"], "a" * 32)
        self.assertEqual(result["OTEL_SPAN_ID"], "b" * 16)
        # CLI 关闭时不下发 CLI 专属开关与 TRACEPARENT
        self.assertNotIn("CLAUDE_CODE_ENABLE_TELEMETRY", result)
        self.assertNotIn("CODEX_OTEL_ENABLED", result)
        self.assertNotIn("TRACEPARENT", result)

    def test_env_cli_vars_injected_when_cli_enabled(self) -> None:
        """CLI 原生遥测开启时应追加 CLI 专属开关与 TRACEPARENT。"""
        result = TicketAiAnalysisService._build_provider_env_overrides(
            build_provider(observability_cli_enabled=True),
            observability_config=build_obs_config(),
            session_id="ticket-ai-task-1001",
            traceparent=f"00-{'a' * 32}-{'b' * 16}-01",
            observability_trace={"trace_id": "a" * 32, "span_id": "b" * 16},
        )
        self.assertEqual(result["CLAUDE_CODE_ENABLE_TELEMETRY"], "1")
        self.assertEqual(result["CLAUDE_CODE_ENHANCED_TELEMETRY_BETA"], "1")
        self.assertEqual(result["CODEX_OTEL_ENABLED"], "1")
        self.assertEqual(result["OTEL_TRACES_EXPORTER"], "otlp")
        self.assertEqual(result["TRACEPARENT"], f"00-{'a' * 32}-{'b' * 16}-01")

    def test_env_otel_skipped_when_disabled(self) -> None:
        """可观测未启用时不注入任何 OTEL 变量。"""
        result = TicketAiAnalysisService._build_provider_env_overrides(
            build_provider(observability_enabled=False),
        )
        self.assertFalse(any(key.startswith("OTEL_") for key in result))


if __name__ == "__main__":
    unittest.main()