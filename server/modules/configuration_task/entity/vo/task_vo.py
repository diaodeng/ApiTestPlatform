"""配置任务运行域接口契约，统一使用 camelCase 和 Pydantic 校验。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

TaskStatus = Literal["ACTIVE", "DISABLED"]
VersionStatus = Literal["DRAFT", "PUBLISHED", "DEPRECATED"]
RunStatus = Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]
TASK_VARIABLES_MAX_BYTES = 64 * 1024
TASK_STEPS_MAX_BYTES = 512 * 1024
TASK_BINDINGS_MAX_BYTES = 64 * 1024


class TaskBaseModel(BaseModel):
    """任务接口模型基础类，兼容 ORM 属性并对外使用驼峰字段。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class ConfigurationTaskCreateModel(TaskBaseModel):
    """创建配置任务请求；Agent 归属和变量以任务级配置为准。"""

    task_name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=500)
    agent_code: str = Field(min_length=1, max_length=128)
    variables: dict[str, Any] = Field(default_factory=dict)
    remark: str = Field(default="", max_length=2000)

    @field_validator("agent_code", "task_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """去掉首尾空白并拒绝空文本。"""
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("任务文本字段不能为空")
        return normalized


class ConfigurationTaskUpdateModel(TaskBaseModel):
    """更新配置任务请求；不修改已发布版本，版本需走独立发布流程。"""

    task_name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    agent_code: str | None = Field(default=None, min_length=1, max_length=128)
    variables: dict[str, Any] | None = None
    status: TaskStatus | None = None
    remark: str | None = Field(default=None, max_length=2000)


class ConfigurationTaskDetailModel(TaskBaseModel):
    """任务详情响应；taskId 和 versionId 按字符串返回。"""

    task_id: str
    task_name: str
    description: str
    agent_code: str
    variables: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus
    current_version_id: str | None = None
    current_version_no: int | None = None
    create_by: str = ""
    create_time: datetime | None = None
    update_by: str = ""
    update_time: datetime | None = None
    remark: str = ""


class TaskVersionCreateModel(TaskBaseModel):
    """创建任务版本草稿请求；输入绑定只允许 fileKey 到资源 ID 的映射。"""

    start_url: str = Field(min_length=1, max_length=512)
    browser_name: str = Field(default="chromium", min_length=1, max_length=32)
    headless: bool = False
    credential_binding_id: str = Field(default="", max_length=64)
    variables: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    input_bindings: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("start_url", mode="before")
    @classmethod
    def validate_start_url(cls, value: str) -> str:
        """起始 URL 必须是 http/https 的绝对地址。"""
        normalized = str(value or "").strip()
        if not normalized.lower().startswith(("http://", "https://")):
            raise ValueError("startUrl 必须是 http/https 地址")
        return normalized

    @field_validator("browser_name", mode="before")
    @classmethod
    def normalize_browser_name(cls, value: str) -> str:
        """浏览器名称小写归一化。"""
        return str(value or "").strip().lower()

    @field_validator("credential_binding_id", mode="before")
    @classmethod
    def normalize_credential_id(cls, value: str) -> str:
        """凭证绑定 ID 去空白。"""
        return str(value or "").strip()

    @field_validator("input_bindings")
    @classmethod
    def validate_input_bindings(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        """fileKey 非空、资源 ID 去空且每键最多 20 个资源。"""
        normalized: dict[str, list[str]] = {}
        for file_key, resource_ids in (value or {}).items():
            key = str(file_key or "").strip()
            if not key or len(key) > 128:
                raise ValueError("fileKey 不能为空且长度不能超过 128")
            ids: list[str] = []
            for item in resource_ids or []:
                resource_id = str(item or "").strip()
                if not resource_id:
                    continue
                if not resource_id.isdigit():
                    raise ValueError(f"fileKey {key} 的资源ID必须是数字字符串")
                if resource_id not in ids:
                    ids.append(resource_id)
            if not ids:
                raise ValueError(f"fileKey {key} 至少绑定一个资源ID")
            if len(ids) > 20:
                raise ValueError(f"fileKey {key} 绑定资源数超过 20")
            normalized[key] = ids
        return normalized


class TaskVersionUpdateModel(TaskBaseModel):
    """更新版本草稿请求；已发布版本不允许更新。"""

    start_url: str | None = Field(default=None, min_length=1, max_length=512)
    browser_name: str | None = Field(default=None, min_length=1, max_length=32)
    headless: bool | None = None
    credential_binding_id: str | None = Field(default=None, max_length=64)
    variables: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None
    input_bindings: dict[str, list[str]] | None = None


class TaskVersionPublishModel(TaskBaseModel):
    """发布版本请求；发布前校验资源 READY、Agent 登记和步骤非空。"""

    pass


class TaskVersionDetailModel(TaskBaseModel):
    """任务版本响应；versionId 和 taskId 按字符串返回。"""

    version_id: str
    task_id: str
    version_no: int
    status: VersionStatus
    start_url: str
    browser_name: str
    headless: bool
    credential_binding_id: str
    variables: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    input_bindings: dict[str, list[str]] = Field(default_factory=dict)
    publish_by: str = ""
    publish_time: datetime | None = None
    create_by: str = ""
    create_time: datetime | None = None
    update_by: str = ""
    update_time: datetime | None = None


class TaskRunCreateModel(TaskBaseModel):
    """创建运行请求；版本号可选，默认使用任务当前发布版本。"""

    agent_code: str | None = Field(default=None, min_length=1, max_length=128)
    version_no: int | None = Field(default=None, ge=1)
    trigger_type: str = Field(default="manual", max_length=32)

    @field_validator("agent_code", "trigger_type", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        """可选文本去空白，空值按未传处理。"""
        if value is None:
            return None
        return str(value).strip() or None


class TaskRunDetailModel(TaskBaseModel):
    """任务运行响应；运行ID、任务ID和版本ID按字符串返回。"""

    task_run_id: str
    task_id: str
    task_version_id: str
    version_no: int
    agent_code: str
    trigger_type: str
    status: RunStatus
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    create_by: str = ""
    create_time: datetime | None = None


class TaskRunQueryModel(TaskBaseModel):
    """运行列表查询参数。"""

    task_id: str | None = None
    agent_code: str | None = None
    status: RunStatus | None = None
    limit: int = Field(default=50, ge=1, le=200)
