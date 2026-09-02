import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
        "observability_cli_enabled": True,
        "provider_code": "obs-provider",
        "platform_code": "custom",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TicketAiObservabilityServiceTests(unittest.TestCase):
    """验证工单 AI 可观测上报的配置解析与 OTLP payload 组装。"""

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

    def test_report_task_span_builds_otlp_payload(self) -> None:
        """任务span应包含 input.value/output.value/gen_ai.usage/session.id 并复用traceId。"""
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers

            class FakeResponse:
                status_code = 200
                text = ""

            return FakeResponse()

        config = TicketAiObservabilityService.build_provider_config(build_provider())
        with patch(
            "modules.ticket.service.ai.ticket_ai_observability_service.httpx.post",
            side_effect=fake_post,
        ):
            TicketAiObservabilityService.report_task_span(
                config,
                task_id=1001,
                ticket_id=2002,
                model_name="test-model",
                prompt_text="测试输入",
                result_text="测试输出",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                latency_ms=120.5,
                success=True,
                trace_id="a" * 32,
                span_id="b" * 16,
            )
        self.assertEqual(captured["url"], "https://observe.example/observe/v1/traces")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer obs-key-123")
        span = captured["json"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["traceId"], "a" * 32)
        self.assertEqual(span["spanId"], "b" * 16)
        attrs = {attr["key"]: attr["value"] for attr in span["attributes"]}
        self.assertEqual(attrs["input.value"]["stringValue"], "测试输入")
        self.assertEqual(attrs["output.value"]["stringValue"], "测试输出")
        self.assertEqual(attrs["gen_ai.usage.input_tokens"]["intValue"], 10)
        self.assertEqual(attrs["gen_ai.usage.output_tokens"]["intValue"], 5)
        self.assertEqual(attrs["gen_ai.request.model"]["stringValue"], "test-model")
        self.assertEqual(attrs["session.id"]["stringValue"], "ticket-ai-task-1001")

    def test_report_task_span_skips_without_config(self) -> None:
        """config 为 None 时应直接跳过，不发起网络请求。"""
        with patch(
            "modules.ticket.service.ai.ticket_ai_observability_service.httpx.post"
        ) as mock_post:
            TicketAiObservabilityService.report_task_span(
                None, task_id=1, ticket_id=1, model_name=None, prompt_text=None, result_text=None
            )
            mock_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()