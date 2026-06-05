from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class AiProviderBaseModel(BaseModel):
    """
    AI Provider 基础模型，用于新增、编辑和详情返回。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    provider_id: int | None = None
    provider_code: str | None = Field(default=None, description="Provider编码")
    provider_name: str | None = Field(default=None, description="Provider名称")
    provider_type: str | None = Field(default=None, description="Provider类型")
    agent_code: str | None = Field(default=None, description="绑定Agent编码")
    model_name: str | None = Field(default=None, description="默认模型名称")
    provider_level: int | None = Field(default=0, description="Provider等级")
    base_url: str | None = Field(default=None, description="API基础地址")
    api_key_prefix: str | None = Field(default=None, description="密钥掩码前缀")
    api_key: str | None = Field(default=None, description="密钥明文，仅创建或更新时提交")
    enabled: bool | None = Field(default=True, description="是否启用")
    extra_config: dict[str, Any] | None = Field(default=None, description="扩展配置")
    remark: str | None = Field(default=None, description="备注")
    has_secret: bool | None = Field(default=False, description="是否已配置密钥")
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
        self.provider_code = str(self.provider_code or "").strip() or None
        self.provider_name = str(self.provider_name or "").strip() or None
        self.provider_type = str(self.provider_type or "").strip() or None
        self.agent_code = str(self.agent_code or "").strip() or None
        self.model_name = str(self.model_name or "").strip() or None
        self.base_url = str(self.base_url or "").strip() or None
        self.api_key_prefix = str(self.api_key_prefix or "").strip() or None
        self.api_key = str(self.api_key or "").strip() or None
        self.remark = str(self.remark or "").strip() or None
        self.enabled = bool(self.enabled)
        self.provider_level = int(self.provider_level or 0)
        return self


class AiProviderQueryModel(BaseModel):
    """
    AI Provider 查询模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    keyword: str | None = Field(default=None, description="关键字，匹配编码、名称、模型或Agent")
    provider_type: str | None = Field(default=None, description="Provider类型")
    enabled: bool | None = Field(default=None, description="是否启用")


@as_query
class AiProviderPageQueryModel(AiProviderQueryModel):
    """
    AI Provider 分页查询模型。
    """

    page_num: int = 1
    page_size: int = 10


class CreateAiProviderModel(AiProviderBaseModel):
    """
    新增 AI Provider 请求模型。
    """

    provider_code: str = Field(description="Provider编码")
    provider_name: str = Field(description="Provider名称")
    provider_type: str = Field(description="Provider类型")
    model_name: str = Field(description="默认模型名称")
    api_key: str = Field(description="Provider密钥明文")


class UpdateAiProviderModel(AiProviderBaseModel):
    """
    编辑 AI Provider 请求模型。
    """

    provider_id: int = Field(description="Provider主键")
    api_key: str | None = Field(default=None, description="Provider密钥明文，不填写则保持不变")


class AiProviderOptionModel(BaseModel):
    """
    AI Provider 下拉选项模型。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    provider_id: int | None = None
    provider_code: str | None = None
    provider_name: str | None = None
    provider_type: str | None = None
    agent_code: str | None = None
    model_name: str | None = None
    provider_level: int | None = None
    base_url: str | None = None
    enabled: bool | None = None


class AiProviderDetailModel(AiProviderBaseModel):
    """
    AI Provider 详情模型。
    """

    pass
