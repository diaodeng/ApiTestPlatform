from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


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
    platform_code: str | None = Field(default=None, description="Provider所属平台")
    api_protocol: str | None = Field(default=None, description="Provider API调用协议")
    supported_usages: list[str] = Field(default_factory=list, description="Provider允许的业务用途")
    supported_executors: list[str] = Field(default_factory=list, description="Provider兼容的执行器")
    preferred_agent_code: str | None = Field(default=None, description="Provider首选Agent编码")
    default_model: str | None = Field(default=None, description="Provider默认模型名称")
    provider_level: int | None = Field(default=0, description="Provider等级")
    base_url: str | None = Field(default=None, description="API基础地址")
    api_key_prefix: str | None = Field(default=None, description="密钥掩码前缀")
    api_key: str | None = Field(default=None, description="密钥明文，仅创建或更新时提交")
    enabled: bool | None = Field(default=True, description="是否启用")
    connection_config: dict[str, Any] | None = Field(default=None, description="协议连接扩展配置")
    worker_env: dict[str, Any] | None = Field(default=None, description="Worker环境变量覆盖配置")
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
        self.platform_code = str(self.platform_code or "").strip() or None
        self.api_protocol = str(self.api_protocol or "").strip() or None
        self.supported_usages = [str(item).strip() for item in self.supported_usages if str(item).strip()]
        self.supported_executors = [str(item).strip() for item in self.supported_executors if str(item).strip()]
        self.preferred_agent_code = str(self.preferred_agent_code or "").strip() or None
        self.default_model = str(self.default_model or "").strip() or None
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
    platform_code: str | None = Field(default=None, description="Provider平台")
    api_protocol: str | None = Field(default=None, description="Provider调用协议")
    usage: str | None = Field(default=None, description="业务用途过滤条件")
    executor: str | None = Field(default=None, description="执行器过滤条件")
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
    platform_code: str = Field(description="Provider所属平台")
    api_protocol: str = Field(description="Provider API调用协议")
    supported_usages: list[str] = Field(min_length=1, description="Provider允许的业务用途")
    supported_executors: list[str] = Field(min_length=1, description="Provider兼容的执行器")
    default_model: str = Field(description="默认模型名称")
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
    platform_code: str | None = None
    api_protocol: str | None = None
    supported_usages: list[str] = Field(default_factory=list)
    supported_executors: list[str] = Field(default_factory=list)
    preferred_agent_code: str | None = None
    default_model: str | None = None
    provider_level: int | None = None
    base_url: str | None = None
    enabled: bool | None = None


class AiProviderDetailModel(AiProviderBaseModel):
    """
    AI Provider 详情模型。
    """

    pass


class AiProviderModelCatalogItemModel(BaseModel):
    """AI Provider 模型目录项。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    model_id: str = Field(description="模型标识")
    display_name: str = Field(default="", description="模型展示名称")
    source: str = Field(description="模型目录来源")
    enabled: bool = Field(default=True, description="是否可选")
    discovered_at: datetime | None = Field(default=None, description="最近发现时间")
    last_seen_at: datetime | None = Field(default=None, description="最近见到时间")


class PreviewAiProviderModelCatalogRequest(AiProviderBaseModel):
    """使用当前表单草稿发现模型目录的请求。"""

    api_key: str | None = Field(default=None, description="Provider密钥明文，仅用于本次探测")
    platform_code: str = Field(description="Provider所属平台")
    api_protocol: str = Field(description="Provider API调用协议")

    @model_validator(mode="after")
    def validate_preview_secret_source(self):
        """
        校验草稿探测的密钥来源。
        :return: 当前请求模型
        """
        if not self.provider_id and not self.api_key:
            raise ValueError("新增Provider探测模型时必须填写密钥")
        return self


class TestAiProviderConnectionRequest(PreviewAiProviderModelCatalogRequest):
    """使用当前表单草稿测试指定模型连通性的请求。"""

    default_model: str = Field(description="待测试的默认模型")


class ViewAiProviderSecretModel(BaseModel):
    """查看Provider密钥前的当前用户密码校验请求。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    password: str = Field(min_length=1, description="当前登录用户密码")


class AiProviderSecretModel(BaseModel):
    """Provider密钥明文响应模型，仅在密码校验成功后返回。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    provider_id: int = Field(description="Provider主键")
    api_key: str = Field(description="Provider密钥明文")
