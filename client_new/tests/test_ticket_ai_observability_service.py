import unittest
from unittest.mock import patch

from services.ticket_ai_observability_service import TicketAiObservabilityService


ENV_OVERRIDES = {
    "OTEL_EXPORTER_OTLP_ENDPOINT": "https://observe.example/observe",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer obs-key-123",
    "OTEL_SERVICE_NAME": "ticket-ai-analysis",
    "OTEL_SESSION_ID": "ticket-ai-task-1001",
    "OTEL_TRACE_ID": "a" * 32,
    "OTEL_SPAN_ID": "b" * 16,
}


class TicketAiObservabilityServiceTests(unittest.TestCase):
    """验证 Agent 侧任务级 span 上报。"""

    def test_build_config_from_env(self) -> None:
        """应从 providerEnv 解析端点、鉴权头、service name 与 trace 上下文。"""
        config = TicketAiObservabilityService.build_config_from_env(ENV_OVERRIDES)
        self.assertEqual(config["endpoint"], "https://observe.example/observe")
        self.assertEqual(config["authorization"], "Bearer obs-key-123")
        self.assertEqual(config["service_name"], "ticket-ai-analysis")
        self.assertEqual(config["session_id"], "ticket-ai-task-1001")
        self.assertEqual(config["trace_id"], "a" * 32)
        self.assertEqual(config["span_id"], "b" * 16)

    def test_build_config_from_env_missing_parts(self) -> None:
        """缺少端点或鉴权头时应返回 None。"""
        self.assertIsNone(TicketAiObservabilityService.build_config_from_env(None))
        self.assertIsNone(TicketAiObservabilityService.build_config_from_env({}))
        self.assertIsNone(
            TicketAiObservabilityService.build_config_from_env(
                {"OTEL_EXPORTER_OTLP_ENDPOINT": "https://observe.example/observe"}
            )
        )

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

        with patch(
            "services.ticket_ai_observability_service.httpx.post",
            side_effect=fake_post,
        ):
            TicketAiObservabilityService.report_task_span(
                ENV_OVERRIDES,
                task_id=1001,
                ticket_id=2002,
                model_name="test-model",
                system_name="codex",
                prompt_text="测试输入",
                result_text="测试输出",
                token_usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                latency_ms=120.5,
                success=True,
            )
        self.assertEqual(captured["url"], "https://observe.example/observe/v1/traces")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer obs-key-123")
        span = captured["json"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["name"], "ticket_ai_analysis")
        self.assertEqual(span["traceId"], "a" * 32)
        self.assertEqual(span["spanId"], "b" * 16)
        attrs = {attr["key"]: attr["value"] for attr in span["attributes"]}
        self.assertEqual(attrs["input.value"]["stringValue"], "测试输入")
        self.assertEqual(attrs["output.value"]["stringValue"], "测试输出")
        self.assertEqual(attrs["gen_ai.usage.input_tokens"]["intValue"], 10)
        self.assertEqual(attrs["gen_ai.usage.output_tokens"]["intValue"], 5)
        self.assertEqual(attrs["gen_ai.request.model"]["stringValue"], "test-model")
        self.assertEqual(attrs["session.id"]["stringValue"], "ticket-ai-task-1001")

    def test_report_task_span_failure_marks_error_status(self) -> None:
        """失败任务应携带 error 属性与 OTLP ERROR 状态。"""
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["json"] = json

            class FakeResponse:
                status_code = 200
                text = ""

            return FakeResponse()

        with patch(
            "services.ticket_ai_observability_service.httpx.post",
            side_effect=fake_post,
        ):
            TicketAiObservabilityService.report_task_span(
                ENV_OVERRIDES,
                task_id=1002,
                ticket_id=2002,
                model_name="test-model",
                system_name="claude",
                prompt_text="失败输入",
                result_text=None,
                success=False,
                error_code="AI_WORKER_TIMEOUT",
                error_message="执行超时",
            )
        span = captured["json"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        self.assertEqual(span["status"]["code"], 2)
        attrs = {attr["key"]: attr["value"] for attr in span["attributes"]}
        self.assertEqual(attrs["error.type"]["stringValue"], "AI_WORKER_TIMEOUT")
        self.assertEqual(attrs["output.value"]["stringValue"], "执行超时")

    def test_report_task_span_skips_without_config(self) -> None:
        """未下发 OTEL 配置时应直接跳过，不发起网络请求。"""
        with patch(
            "services.ticket_ai_observability_service.httpx.post"
        ) as mock_post:
            TicketAiObservabilityService.report_task_span(
                {},
                task_id=1,
                ticket_id=1,
                model_name=None,
                system_name=None,
                prompt_text=None,
                result_text=None,
            )
            mock_post.assert_not_called()

    def test_report_task_span_swallows_network_error(self) -> None:
        """网络异常只记日志，不向调用方抛出。"""
        with patch(
            "services.ticket_ai_observability_service.httpx.post",
            side_effect=TimeoutError("connect timeout"),
        ):
            # 不应抛出异常
            TicketAiObservabilityService.report_task_span(
                ENV_OVERRIDES,
                task_id=1,
                ticket_id=1,
                model_name=None,
                system_name="codex",
                prompt_text=None,
                result_text=None,
            )


if __name__ == "__main__":
    unittest.main()