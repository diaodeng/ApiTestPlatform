"""轻量AI测试工作台选项接口回归测试。"""
import unittest
from types import SimpleNamespace

from modules.ticket.service.ai.ticket_light_ai_test_service import TASK_DEFAULT_PROMPT_CODES, TicketLightAiTestService


def _fake_query_db():
    """桩数据库会话：options 查询仅依赖传入的桩数据。"""
    return SimpleNamespace()


class _ListOptionsStub:
    """把 options 依赖的方法替换为返回桩数据的上下文管理器。"""

    def __init__(self, providers, models, templates):
        self.providers = providers
        self.models = models
        self.templates = templates

    def __enter__(self):
        from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
        from module_admin.service.ai_provider_model_catalog_service import AiProviderModelCatalogService
        from module_admin.service.ai_provider_service import AiProviderService

        self._orig_provider = AiProviderService.get_ai_provider_options_services
        self._orig_models = AiProviderModelCatalogService.list_model_options_by_provider_code
        self._orig_templates = AiPromptTemplateService.get_prompt_template_options_services
        AiProviderService.get_ai_provider_options_services = classmethod(
            lambda cls, db, usage=None, executor=None: self.providers
        )
        AiProviderModelCatalogService.list_model_options_by_provider_code = classmethod(
            lambda cls, db, provider_code: self.models.get(provider_code, [])
        )
        AiPromptTemplateService.get_prompt_template_options_services = classmethod(
            lambda cls, db, enabled_only=True: self.templates
        )
        return self

    def __exit__(self, *args):
        from module_admin.service.ai_prompt_template_service import AiPromptTemplateService
        from module_admin.service.ai_provider_model_catalog_service import AiProviderModelCatalogService
        from module_admin.service.ai_provider_service import AiProviderService

        AiProviderService.get_ai_provider_options_services = self._orig_provider
        AiProviderModelCatalogService.list_model_options_by_provider_code = self._orig_models
        AiPromptTemplateService.get_prompt_template_options_services = self._orig_templates
        return False


class TicketAiTestOptionsTests(unittest.TestCase):
    """get_test_options 结构回归测试。"""

    def test_get_test_options_builds_template_task_type_mapping(self):
        """模板选项应携带任务类型归属映射，且不因遍历字典解包错误而崩溃。

        回归：曾把 TASK_DEFAULT_PROMPT_CODES.items() 解包出的字符串误当字典取
        task["value"]，导致 /ticket/ai-test/options 500（string indices must be integers）。
        """
        providers = [
            SimpleNamespace(
                provider_code="openai_com",
                provider_name="公司-deepseek-flash",
                default_model="deepseek-v4-flash",
            )
        ]
        models = {"openai_com": [SimpleNamespace(model_id="deepseek-v4-flash", display_name="DeepSeek Flash")]}
        templates = [
            SimpleNamespace(template_code=code, template_name=code)
            for code in TASK_DEFAULT_PROMPT_CODES.values()
        ]
        templates.append(SimpleNamespace(template_code="ticket_analysis_append_default", template_name="非默认模板"))

        with _ListOptionsStub(providers, models, templates):
            result = TicketLightAiTestService.get_test_options(_fake_query_db())

        self.assertEqual(len(result["taskTypes"]), 5)
        self.assertEqual(result["providers"][0]["providerCode"], "openai_com")
        self.assertEqual(result["providerModels"]["openai_com"][0]["modelId"], "deepseek-v4-flash")
        by_code = {item["templateCode"]: item for item in result["promptTemplates"]}
        self.assertEqual(by_code["ticket_sync_extract_default"]["taskTypes"], ["sync_extract"])
        self.assertTrue(by_code["ticket_sync_extract_default"]["isDefault"])
        # 非默认模板的 taskTypes 应为空列表
        non_default = [item for item in result["promptTemplates"] if not item["isDefault"]]
        self.assertTrue(non_default)
        for item in non_default:
            self.assertEqual(item["taskTypes"], [])


if __name__ == "__main__":
    unittest.main()
