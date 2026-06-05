from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class AiPromptTemplateBaseModel(BaseModel):
    """
    AI 提示词模板基础模型，用于新增、编辑和详情返回。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    template_id: int | None = None
    template_code: str | None = Field(default=None, description="模板编码")
    template_name: str | None = Field(default=None, description="模板名称")
    template_category: str | None = Field(default=None, description="模板分类")
    provider_code: str | None = Field(default=None, description="默认Provider编码")
    model_name: str | None = Field(default=None, description="默认模型名称")
    prompt_content: str | None = Field(default=None, description="提示词内容")
    enabled: bool | None = Field(default=True, description="是否启用")
    sort: int | None = Field(default=0, description="排序")
    extra_config: dict[str, Any] | None = Field(default=None, description="扩展配置")
    remark: str | None = Field(default=None, description="备注")
    create_by: str | None = None
    create_time: datetime | None = None
    update_by: str | None = None
    update_time: datetime | None = None

    @model_validator(mode="after")
    def normalize_common_fields(self):
        """
        归一化通用字段。
        :return: 当前模型
        """
        self.template_code = str(self.template_code or "").strip() or None
        self.template_name = str(self.template_name or "").strip() or None
        self.template_category = str(self.template_category or "").strip() or None
        self.provider_code = str(self.provider_code or "").strip() or None
        self.model_name = str(self.model_name or "").strip() or None
        self.prompt_content = str(self.prompt_content or "").strip() or None
        self.remark = str(self.remark or "").strip() or None
        self.enabled = bool(self.enabled)
        self.sort = int(self.sort or 0)
        return self


class AiPromptTemplateQueryModel(BaseModel):
    """
    AI 提示词模板查询模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    keyword: str | None = Field(default=None, description="关键字，匹配编码、名称、分类或Provider")
    template_category: str | None = Field(default=None, description="模板分类")
    enabled: bool | None = Field(default=None, description="是否启用")


@as_query
class AiPromptTemplatePageQueryModel(AiPromptTemplateQueryModel):
    """
    AI 提示词模板分页查询模型。
    """

    page_num: int = 1
    page_size: int = 10


class CreateAiPromptTemplateModel(AiPromptTemplateBaseModel):
    """
    新增 AI 提示词模板请求模型。
    """

    template_code: str = Field(description="模板编码")
    template_name: str = Field(description="模板名称")
    template_category: str = Field(description="模板分类")
    prompt_content: str = Field(description="提示词内容")


class UpdateAiPromptTemplateModel(AiPromptTemplateBaseModel):
    """
    编辑 AI 提示词模板请求模型。
    """

    template_id: int = Field(description="模板主键")


class AiPromptTemplateOptionModel(BaseModel):
    """
    AI 提示词模板下拉选项模型。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    template_id: int | None = None
    template_code: str | None = None
    template_name: str | None = None
    template_category: str | None = None
    provider_code: str | None = None
    model_name: str | None = None
    enabled: bool | None = None
    sort: int | None = None


class AiPromptTemplateDetailModel(AiPromptTemplateBaseModel):
    """
    AI 提示词模板详情模型。
    """

    pass
