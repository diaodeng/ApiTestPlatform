from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


class CredentialBaseModel(BaseModel):
    """凭证接口模型基础类。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class CredentialAuthConfigModel(CredentialBaseModel):
    """HTTP 或浏览器登录刷新配置；账号、密码和 OTP 秘钥应放入 secret。"""

    login_url: str = ""
    refresh_url: str = ""
    request_method: Literal["GET", "POST", "PUT", "PATCH"] = "POST"
    request_template: dict[str, Any] = Field(default_factory=dict)
    response_mapping: dict[str, Any] = Field(default_factory=dict)
    login_method: Literal["GET", "POST", "PUT", "PATCH"] = "POST"
    refresh_method: Literal["GET", "POST", "PUT", "PATCH"] = "POST"
    login_request_template: dict[str, Any] = Field(default_factory=dict)
    login_response_mapping: dict[str, Any] = Field(default_factory=dict)
    refresh_request_template: dict[str, Any] = Field(default_factory=dict)
    refresh_response_mapping: dict[str, Any] = Field(default_factory=dict)
    browser_start_url: str = ""
    otp_type: Literal["none", "totp", "sms", "email", "manual"] = "none"
    target_host_patterns: list[str] = Field(default_factory=list)

    @field_validator(
        "request_template",
        "response_mapping",
        "login_request_template",
        "login_response_mapping",
        "refresh_request_template",
        "refresh_response_mapping",
        mode="before",
    )
    @classmethod
    def normalize_nullable_json_object(cls, value):
        """数据库旧记录中的 JSON NULL 统一转换为空对象。"""
        return {} if value is None else value

    @field_validator("target_host_patterns", mode="before")
    @classmethod
    def normalize_nullable_host_patterns(cls, value):
        """数据库旧记录中的域名范围 NULL 统一转换为空列表。"""
        return [] if value is None else value


class CredentialSaveModel(CredentialBaseModel):
    """新增或更新凭证请求。secret 是结构化敏感内容，只在写入时接收。"""

    credential_name: str = Field(min_length=1, max_length=128)
    credential_type: Literal["browser_storage", "http_cookie", "http_token", "http_api_key", "http_header"]
    auth_mode: Literal["manual", "http_login", "http_refresh", "browser_login", "browser_refresh"] = "manual"
    enabled: bool = True
    auto_refresh_enabled: bool = False
    refresh_interval_sec: int = Field(default=0, ge=0, le=2592000)
    sharing_mode: Literal["shared_read", "exclusive_refresh", "exclusive_use"] = "shared_read"
    secret: dict[str, Any] = Field(default_factory=dict)
    expire_time: datetime | None = None
    auth_config: CredentialAuthConfigModel = Field(default_factory=CredentialAuthConfigModel)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_refresh_configuration(self):
        """校验自动刷新与认证方式关系，静态 API Key 不会被误加入刷新队列。"""
        if self.auto_refresh_enabled and self.auth_mode in {"manual", "browser_login", "browser_refresh"}:
            raise ValueError("当前认证方式没有可执行的刷新流程，请选择 HTTP 刷新或浏览器刷新方式")
        if self.auto_refresh_enabled and self.refresh_interval_sec <= 0:
            raise ValueError("开启自动刷新时必须设置刷新间隔")
        if self.auto_refresh_enabled and self.auth_mode == "http_login" and self.auth_config.otp_type not in {"none", "totp"}:
            raise ValueError("短信、邮箱或人工确认 OTP 不能由定时任务自动完成")
        if self.auto_refresh_enabled and self.auth_mode == "http_login" and not self.auth_config.login_url:
            raise ValueError("HTTP 登录自动刷新必须配置登录地址")
        if self.auto_refresh_enabled and self.auth_mode == "http_refresh" and not self.auth_config.refresh_url:
            raise ValueError("HTTP 刷新必须配置刷新地址")
        return self


class CredentialUpdateModel(CredentialSaveModel):
    """更新凭证请求，expected_revision 防止刷新和人工编辑相互覆盖。"""

    expected_revision: int = Field(ge=1)


class CredentialModel(CredentialBaseModel):
    """不含任何明文凭证的凭证详情响应。"""

    credential_id: str
    credential_name: str
    credential_type: str
    auth_mode: str
    enabled: bool
    auto_refresh_enabled: bool
    refresh_interval_sec: int
    sharing_mode: str
    secret_mask: str
    revision: int
    expire_time: datetime | None = None
    last_refresh_time: datetime | None = None
    last_refresh_status: str
    last_refresh_message: str
    auth_config: CredentialAuthConfigModel = Field(default_factory=CredentialAuthConfigModel)
    remark: str | None = None
    create_by: str | None = None
    create_time: datetime | None = None
    update_by: str | None = None
    update_time: datetime | None = None


@as_query
class CredentialQueryModel(CredentialBaseModel):
    """凭证列表查询参数。"""

    keyword: str = ""
    enabled: bool | None = None


class CredentialBindingSaveModel(CredentialBaseModel):
    """业务凭证绑定请求。"""

    binding_name: str = Field(min_length=1, max_length=128)
    credential_id: str
    business_type: Literal["web_case", "ticket_log_pull", "ticket_remote_sync"]
    projection_type: Literal["playwright_storage", "http_cookie", "http_header"]
    target_url: str = ""
    target_host_patterns: list[str] = Field(default_factory=list)
    sharing_mode: Literal["shared_read", "exclusive_refresh", "exclusive_use"] = "shared_read"
    writeback_enabled: bool = False
    enabled: bool = True
    remark: str | None = None


class CredentialBindingModel(CredentialBindingSaveModel):
    """业务凭证绑定响应。"""

    binding_id: str
    credential_name: str = ""
    credential_type: str = ""
    create_time: datetime | None = None
    update_time: datetime | None = None


@as_query
class CredentialBindingQueryModel(CredentialBaseModel):
    """绑定列表查询参数。"""

    business_type: str | None = None


@as_query
class CredentialBindingOptionQueryModel(CredentialBaseModel):
    """绑定选项查询参数；业务类型使用 camelCase 对外暴露。"""

    business_type: Literal["web_case", "ticket_log_pull", "ticket_remote_sync"]


class CredentialRefreshRequestModel(CredentialBaseModel):
    """手工触发刷新请求。"""

    expected_revision: int = Field(ge=1)
    otp_code: str | None = Field(default=None, min_length=1, max_length=32)


class CredentialWritebackModel(CredentialBaseModel):
    """浏览器刷新任务写回 storageState 的专用请求。"""

    expected_revision: int = Field(ge=1)
    storage_state: dict[str, Any]
    local_cache_enabled: bool = False


class CredentialOptionModel(CredentialBaseModel):
    """业务配置选择凭证绑定时的下拉项。"""

    binding_id: str
    binding_name: str
    credential_name: str
    credential_type: str
    projection_type: str
    business_type: str


@as_query
class CredentialOperationLogQueryModel(CredentialBaseModel):
    """统一凭证审计日志查询参数。"""

    credential_id: int | None = None
    limit: int = Field(default=100, ge=1, le=500)


class CredentialOperationLogModel(CredentialBaseModel):
    """统一凭证审计日志脱敏响应。"""

    operation_id: str
    credential_id: str
    binding_id: str | None = None
    operation_type: str
    status: str
    revision: int | None = None
    message: str
    operator: str
    create_time: datetime | None = None


class CredentialLeaseModel(CredentialBaseModel):
    """当前有效租约脱敏响应。"""

    lease_id: str
    credential_id: str
    lease_type: str
    holder: str
    expires_at: datetime
    create_time: datetime | None = None
