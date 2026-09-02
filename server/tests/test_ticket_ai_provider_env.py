import unittest
from types import SimpleNamespace
from unittest.mock import patch

from module_admin.service.ai_provider_service import AiProviderService
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


class TicketAiProviderEnvTests(unittest.TestCase):
    """验证工单 AI 分析下发的 Provider 核心连接配置优先级。"""

    @patch(
        "modules.ticket.service.ai.ticket_ai_analysis_service.ApiKeyUtil.decrypt_api_key",
        return_value="provider-key",
    )
    def test_provider_core_connection_values_override_worker_env(self, _decrypt_api_key):
        """workerEnv 不能覆盖当前选中 Provider 的密钥、地址和模型。"""
        provider = SimpleNamespace(
            api_key_cipher_text="encrypted-key",
            api_protocol="openai_chat_completions",
            base_url="https://provider.example/v1",
            default_model="provider-model",
            provider_code="provider-code",
            provider_name="Provider",
            platform_code="openai_compatible",
            provider_level=1,
            worker_env={
                "OPENAI_API_KEY": "old-key",
                "OPENAI_BASE_URL": "https://old.example/v1",
                "OPENAI_MODEL": "old-model",
                "WORKER_TIMEOUT": "30",
            },
        )

        result = TicketAiAnalysisService._build_provider_env_overrides(provider)

        self.assertEqual(result["OPENAI_API_KEY"], "provider-key")
        self.assertEqual(result["OPENAI_BASE_URL"], "https://provider.example/v1")
        self.assertEqual(result["OPENAI_MODEL"], "provider-model")
        self.assertEqual(result["WORKER_TIMEOUT"], "30")


def test_observability_disabled_preserves_config() -> None:
    """关闭可观测开关时应保留端点等配置，不得清空（隐藏字段不清空规范）。"""
    from types import SimpleNamespace

    page_object = SimpleNamespace(
        observability_enabled=False,
        observability_endpoint="https://observe.example/observe",
        observability_auth_type="basic",
        observability_service_name="custom-name",
        observability_cli_enabled=True,
        observability_api_key="",
    )
    result = AiProviderService._validate_observability(page_object, has_stored_secret=True)
    assert result["observability_enabled"] is False
    assert result["observability_endpoint"] == "https://observe.example/observe"
    assert result["observability_auth_type"] == "basic"
    assert result["observability_service_name"] == "custom-name"
    # 总开关关闭时，CLI 遥测子开关必须一并停用
    assert result["observability_cli_enabled"] is False


if __name__ == "__main__":
    unittest.main()
