from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.entity.vo.ai_prompt_template_vo import AiPromptTemplateOptionModel
from module_admin.entity.vo.ai_provider_vo import AiProviderOptionModel


class AiConfigSummaryItemModel(BaseModel):
    """
    AI 聚合配置项模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    field_name: str = Field(default="", description="前端字段名")
    config_key: str = Field(default="", description="系统参数键名")
    config_name: str = Field(default="", description="系统参数名称")
    current_value: str | None = Field(default=None, description="当前值")
    default_value: str | None = Field(default=None, description="默认值")
    remark: str | None = Field(default=None, description="备注")


class AiConfigSummaryModel(BaseModel):
    """
    AI 聚合配置页面返回模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    translate_provider_code: str | None = Field(default=None, description="翻译Provider编码")
    translate_prompt_code: str | None = Field(default=None, description="翻译提示词编码")
    translate_enabled: bool | None = Field(default=None, description="是否启用工单翻译")
    title_summary_enabled: bool | None = Field(default=None, description="是否启用工单标题总结")
    title_summary_provider_code: str | None = Field(default=None, description="工单标题总结Provider编码")
    title_summary_prompt_code: str | None = Field(default=None, description="工单标题总结提示词编码")
    category_classify_enabled: bool | None = Field(default=None, description="是否启用工单自动分类")
    category_classify_provider_code: str | None = Field(default=None, description="工单自动分类Provider编码")
    category_classify_prompt_code: str | None = Field(default=None, description="工单自动分类提示词编码")
    log_extract_enabled: bool | None = Field(default=None, description="是否启用工单日志参数提取")
    log_extract_provider_code: str | None = Field(default=None, description="工单日志参数提取Provider编码")
    log_extract_prompt_code: str | None = Field(default=None, description="工单日志参数提取提示词编码")
    knowledge_provider_code: str | None = Field(default=None, description="知识提炼Provider编码")
    knowledge_prompt_code: str | None = Field(default=None, description="知识提炼提示词编码")
    analysis_worker_command: str | None = Field(default=None, description="分析Worker命令")
    analysis_worker_model: str | None = Field(default=None, description="分析Worker模型")
    analysis_worker_sandbox: str | None = Field(default=None, description="分析Worker沙箱")
    analysis_worker_timeout_sec: int | None = Field(default=None, description="分析Worker超时秒数")
    analysis_workspace_root: str | None = Field(default=None, description="分析工作区根目录")
    analysis_agent_code: str | None = Field(default=None, description="分析Agent编码")
    config_rows: list[AiConfigSummaryItemModel] = Field(default_factory=list, description="配置明细")
    provider_options: list[AiProviderOptionModel] = Field(default_factory=list, description="Provider选项")
    prompt_options: dict[str, list[AiPromptTemplateOptionModel]] = Field(default_factory=dict, description="提示词选项")
    quick_links: list[dict[str, Any]] = Field(default_factory=list, description="快捷入口")


class AiConfigUpdateModel(BaseModel):
    """
    AI 聚合配置更新模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    translate_provider_code: str | None = Field(default=None, description="翻译Provider编码")
    translate_prompt_code: str | None = Field(default=None, description="翻译提示词编码")
    translate_enabled: bool | None = Field(default=None, description="是否启用工单翻译")
    title_summary_enabled: bool | None = Field(default=None, description="是否启用工单标题总结")
    title_summary_provider_code: str | None = Field(default=None, description="工单标题总结Provider编码")
    title_summary_prompt_code: str | None = Field(default=None, description="工单标题总结提示词编码")
    category_classify_enabled: bool | None = Field(default=None, description="是否启用工单自动分类")
    category_classify_provider_code: str | None = Field(default=None, description="工单自动分类Provider编码")
    category_classify_prompt_code: str | None = Field(default=None, description="工单自动分类提示词编码")
    log_extract_enabled: bool | None = Field(default=None, description="是否启用工单日志参数提取")
    log_extract_provider_code: str | None = Field(default=None, description="工单日志参数提取Provider编码")
    log_extract_prompt_code: str | None = Field(default=None, description="工单日志参数提取提示词编码")
    knowledge_provider_code: str | None = Field(default=None, description="知识提炼Provider编码")
    knowledge_prompt_code: str | None = Field(default=None, description="知识提炼提示词编码")
    analysis_worker_command: str | None = Field(default=None, description="分析Worker命令")
    analysis_worker_model: str | None = Field(default=None, description="分析Worker模型")
    analysis_worker_sandbox: str | None = Field(default=None, description="分析Worker沙箱")
    analysis_worker_timeout_sec: int | None = Field(default=None, description="分析Worker超时秒数")
    analysis_workspace_root: str | None = Field(default=None, description="分析工作区根目录")
    analysis_agent_code: str | None = Field(default=None, description="分析Agent编码")
