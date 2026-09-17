import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query

# 多步登录链单个步骤输出变量的命名约束：仅允许字母开头的标识符，避免渲染占位符时产生歧义。
LOGIN_STEP_VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# 步骤输出允许的提取来源语法：JSON 路径、响应头、响应 Cookie、全部 Set-Cookie，可附加一次 |transform 加工。
LOGIN_STEP_OUTPUT_SOURCE_PREFIXES = ("json:", "header:", "cookie:")
LOGIN_STEP_OUTPUT_MAX_COUNT = 5
LOGIN_STEP_MAX_COUNT = 5


class CredentialBaseModel(BaseModel):
    """凭证接口模型基础类。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class CredentialResponseAssertionModel(CredentialBaseModel):
    """HTTP 登录或刷新接口的业务成功断言。"""

    source: str = Field(min_length=1, max_length=256)
    operator: Literal["equals", "not_equals", "exists", "not_empty", "contains", "in"] = "equals"
    expected: Any = None
    message: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_response_assertion(self):
        """限制断言来源和操作符，避免执行任意表达式。"""
        self.source = self.source.strip()
        valid_source = self.source == "status" or any(
            self.source.startswith(prefix) and len(self.source) > len(prefix)
            for prefix in ("json:", "header:", "cookie:")
        )
        if not valid_source:
            raise ValueError("成功断言来源仅支持 status、json:字段、header:名称或 cookie:名称")
        if self.operator in {"contains", "in"} and self.expected is None:
            raise ValueError(f"成功断言操作符 {self.operator} 必须填写期望值")
        if self.operator == "in" and not isinstance(self.expected, list):
            raise ValueError("成功断言操作符 in 的期望值必须是 JSON 数组")
        return self


class CredentialStepConditionModel(CredentialBaseModel):
    """步骤执行条件：条件不满足时跳过该步骤，用于兼容"部分账号需要 OTP、部分不需要"的站点。

    variable 支持 `step.N.变量`、`step.<步骤id>.变量`（引用更早步骤的输出）和 `secret.字段`
    （引用凭证敏感字段，如 secret.otpSecret 是否存在）。
    """

    variable: str = Field(min_length=1, max_length=128)
    operator: Literal["equals", "not_equals", "contains", "not_contains", "exists", "not_empty"] = "exists"
    value: Any = None
    message: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_condition(self):
        """约束条件变量命名空间与操作符期望值。"""
        self.variable = self.variable.strip()
        namespace = self.variable.split(".", 1)[0] if "." in self.variable else ""
        if namespace not in {"step", "secret"} or "." not in self.variable:
            raise ValueError("条件变量必须以 step. 或 secret. 开头，例如 step.1.result 或 secret.otpSecret")
        value_required = {"equals", "not_equals", "contains", "not_contains"}
        if self.operator in value_required and self.value is None:
            raise ValueError(f"条件操作符 {self.operator} 必须填写比较值")
        if self.operator in value_required and self.value is not None:
            if not isinstance(self.value, (str, int, float, bool)):
                raise ValueError("条件比较值仅支持字符串、数字或布尔值")
        return self


class CredentialLoginStepModel(CredentialBaseModel):
    """多步登录/刷新链中的单个步骤配置。

    请求模板（url、headers、body）支持 ${secret.字段}、${step.N.变量} 和 ${step.<id>.变量}
    三类占位符；outputs 声明本步骤从响应提取的变量：persist_outputs=False 时仅进入本次执行
    上下文（链结束即丢弃），persist_outputs=True 时按响应映射规则写回凭证密文。
    when 条件不满足时跳过本步骤（及其输出），用于同一站点混合"需要/不需要 OTP"的账号。
    """

    id: str = Field(default="", max_length=64)
    name: str = Field(default="", max_length=64)
    url: str = Field(min_length=1, max_length=1000)
    method: Literal["GET", "POST", "PUT", "PATCH"] = "POST"
    body_type: Literal["none", "form", "json", "multipart"] = "form"
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    success_assertions: list[CredentialResponseAssertionModel] = Field(default_factory=list)
    outputs: dict[str, str] = Field(default_factory=dict)
    persist_outputs: bool = False
    # 条件步骤：条件不满足时跳过本步骤；省略表示无条件执行。
    when: CredentialStepConditionModel | None = None

    @field_validator("headers", mode="before")
    @classmethod
    def normalize_nullable_headers(cls, value):
        """数据库旧记录中的 JSON NULL 统一转换为空对象。"""
        return {} if value is None else value

    @field_validator("success_assertions", mode="before")
    @classmethod
    def normalize_nullable_assertions(cls, value):
        """数据库旧记录中的断言 JSON NULL 统一转换为空列表。"""
        return [] if value is None else value

    @field_validator("outputs", mode="before")
    @classmethod
    def normalize_nullable_outputs(cls, value):
        """数据库旧记录中的输出 JSON NULL 统一转换为空对象。"""
        return {} if value is None else value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """仅允许 http/https 地址，防止把内网文件等协议注入登录链。"""
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("登录步骤地址必须以 http:// 或 https:// 开头")
        return value

    @model_validator(mode="after")
    def validate_outputs(self):
        """按步骤类型约束输出键与提取来源语法，非法配置在保存时即报错而不是等到执行期。

        临时输出（persist_outputs=False）的键是步骤变量名，仅允许标识符；
        写回输出（persist_outputs=True）的键是凭证写入目标，支持 header.cookie、
        header.cookie.<名称>、cookies、cookies.<名称> 和普通字段名，与响应映射规则一致。
        """
        if len(self.outputs) > LOGIN_STEP_OUTPUT_MAX_COUNT:
            raise ValueError(f"单个登录步骤最多配置 {LOGIN_STEP_OUTPUT_MAX_COUNT} 个输出变量")
        for output_key, source in self.outputs.items():
            if self.persist_outputs:
                valid_key = (
                    output_key in {"header.cookie", "cookies"}
                    or output_key.startswith("header.cookie.")
                    or output_key.startswith("cookies.")
                    or bool(LOGIN_STEP_VARIABLE_NAME_PATTERN.match(output_key))
                )
            else:
                valid_key = bool(LOGIN_STEP_VARIABLE_NAME_PATTERN.match(output_key))
            if not valid_key:
                raise ValueError(
                    f"输出键 {output_key} 不合法：临时输出必须是标识符（如 ticket），"
                    "写回输出必须是 header.cookie[.名称]、cookies[.名称] 或普通字段名"
                )
            normalized = str(source).strip()
            if normalized != "cookies" and not normalized.startswith(LOGIN_STEP_OUTPUT_SOURCE_PREFIXES):
                raise ValueError(
                    f"输出变量 {output_key} 的提取来源仅支持 json:字段、header:名称、cookie:名称或 cookies"
                )
            self.outputs[output_key] = normalized
        return self

    @field_validator("id")
    @classmethod
    def validate_step_id(cls, value: str) -> str:
        """步骤 id 用于语义化变量引用（${step.<id>.变量}）；不允许纯数字以免与序号引用混淆。"""
        value = value.strip()
        if not value:
            return ""
        if not LOGIN_STEP_VARIABLE_NAME_PATTERN.match(value):
            raise ValueError(f"步骤 id {value} 不合法，仅允许字母开头的字母数字下划线")
        if value.isdigit():
            raise ValueError("步骤 id 不能是纯数字，纯数字会被当作步骤序号")
        return value

    @model_validator(mode="after")
    def validate_body_compatibility(self):
        """GET 请求不允许携带请求体；form/multipart 请求体必须是对象。"""
        if self.method in {"GET"} and self.body_type != "none":
            raise ValueError(f"登录步骤 {self.url} 为 GET 请求，请求体类型必须为 none")
        if self.body_type in {"form", "multipart"} and self.body is not None and not isinstance(self.body, dict):
            raise ValueError("form 或 multipart 请求体必须是 JSON 对象（键值对）")
        return self


# ${step.N.变量} / ${step.<id>.变量} 的引用语法；N 为从 1 开始的步骤序号，id 为语义化步骤标识。
STEP_VARIABLE_REFERENCE_PATTERN = re.compile(r"\$\{step\.([^}.]+)\.([A-Za-z_][A-Za-z0-9_]*)\}")


def validate_login_step_references(steps: list[CredentialLoginStepModel]) -> None:
    """校验多步登录/刷新链的跨步骤变量引用。

    ${step.N.变量} / ${step.<id>.变量} 只允许引用序号或 id 更小（更早执行）步骤声明过的输出变量；
    `when` 条件变量允许引用更早步骤输出或 secret 字段。防止保存配置时留下执行期必然失败的引用。
    """
    ids_seen: set[str] = set()
    for index, step in enumerate(steps, start=1):
        # 可用变量：更早步骤的输出，按序号和语义 id 两种方式引用。
        available: set[str] = set()
        for earlier_index in range(1, index):
            earlier = steps[earlier_index - 1]
            for name in earlier.outputs:
                available.add(f"step.{earlier_index}.{name}")
                if earlier.id:
                    available.add(f"step.{earlier.id}.{name}")
        for template in _iter_step_templates(step):
            if not isinstance(template, str):
                continue
            for match in re.finditer(r"\$\{([^}]+)\}", template):
                reference = match.group(1).strip()
                if reference.startswith("secret."):
                    continue
                if reference in available:
                    continue
                raise ValueError(
                    f"登录步骤 {index} 引用了不存在的变量 ${{{reference}}}；"
                    "步骤只能引用更早步骤声明的输出变量（如 ${step.1.ticket} 或 ${step.login.ticket}）"
                )
        if step.when:
            when_variable = step.when.variable
            if not (when_variable.startswith("secret.") or when_variable in available):
                raise ValueError(
                    f"登录步骤 {index} 的执行条件引用了不存在的变量 {when_variable}；"
                    "条件变量只能引用更早步骤的输出（step.N.变量 或 step.<id>.变量）或凭证字段（secret.字段）"
                )
        if step.id:
            if step.id in ids_seen:
                raise ValueError(f"步骤 id {step.id} 重复，步骤 id 必须唯一")
            ids_seen.add(step.id)


def _iter_step_templates(step: CredentialLoginStepModel):
    """迭代步骤配置中所有参与模板渲染的字符串位置（url、headers 值、body 递归）。"""
    yield step.url
    yield from step.headers.values()
    yield from _iter_strings(step.body)


def _iter_strings(value: Any):
    """递归产出任意 JSON 结构中的字符串叶子节点。"""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


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
    login_success_assertions: list[CredentialResponseAssertionModel] = Field(default_factory=list)
    refresh_request_template: dict[str, Any] = Field(default_factory=dict)
    refresh_response_mapping: dict[str, Any] = Field(default_factory=dict)
    refresh_success_assertions: list[CredentialResponseAssertionModel] = Field(default_factory=list)
    login_steps: list[CredentialLoginStepModel] = Field(default_factory=list)
    refresh_steps: list[CredentialLoginStepModel] = Field(default_factory=list)
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

    @field_validator("login_success_assertions", "refresh_success_assertions", mode="before")
    @classmethod
    def normalize_nullable_success_assertions(cls, value):
        """数据库旧记录中的断言 JSON NULL 统一转换为空列表。"""
        return [] if value is None else value

    @field_validator("login_steps", "refresh_steps", mode="before")
    @classmethod
    def normalize_nullable_login_steps(cls, value):
        """数据库旧记录中的多步链 JSON NULL 统一转换为空列表。"""
        return [] if value is None else value

    @field_validator("target_host_patterns", mode="before")
    @classmethod
    def normalize_nullable_host_patterns(cls, value):
        """数据库旧记录中的域名范围 NULL 统一转换为空列表。"""
        return [] if value is None else value

    @field_validator("login_steps", "refresh_steps")
    @classmethod
    def validate_login_steps(cls, value: list[CredentialLoginStepModel]) -> list[CredentialLoginStepModel]:
        """限制多步链长度，并校验跨步骤变量引用的合法性。"""
        if len(value) > LOGIN_STEP_MAX_COUNT:
            raise ValueError(f"多步登录链最多支持 {LOGIN_STEP_MAX_COUNT} 个步骤")
        validate_login_step_references(value)
        return value


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
        if self.auto_refresh_enabled and self.auth_mode == "http_login":
            if not self.auth_config.login_url and not self.auth_config.login_steps:
                raise ValueError("HTTP 登录自动刷新必须配置登录地址或多步登录链")
        if self.auto_refresh_enabled and self.auth_mode == "http_refresh":
            if not self.auth_config.refresh_url and not self.auth_config.refresh_steps:
                raise ValueError("HTTP 刷新必须配置刷新地址或多步刷新链")
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
    business_type: Literal["web_case", "ticket_log_pull", "ticket_remote_sync", "external_data_query"]
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

    business_type: Literal["web_case", "ticket_log_pull", "ticket_remote_sync", "external_data_query"]


class CredentialRefreshRequestModel(CredentialBaseModel):
    """手工触发刷新请求。"""

    expected_revision: int = Field(ge=1)
    otp_code: str | None = Field(default=None, min_length=1, max_length=32)


class CredentialFlowTestModel(CredentialBaseModel):
    """多步登录/刷新链流程测试请求；只执行认证链，不写回凭证。"""

    flow_type: Literal["login", "refresh"] = "login"
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
