"""配置任务运行域接口契约，统一使用 camelCase 和 Pydantic 校验。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

TaskStatus = Literal["ACTIVE", "DISABLED"]
VersionStatus = Literal["DRAFT", "PUBLISHED", "DEPRECATED"]
RunStatus = Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]
BusinessStatus = Literal["PENDING", "RUNNING", "SUCCESS", "FAILED", "CANCELLED"]
EvidenceType = Literal[
    "checkpoint_screenshot",
    "before_screenshot",
    "after_screenshot",
    "failure_screenshot",
    "execution_log",
    "report",
]
EvidenceMode = Literal["NONE", "OPTIONAL", "REQUIRED", "BEFORE_AFTER"]
EvidenceCompletenessPolicy = Literal["WARN", "BLOCK_ACCEPTANCE", "BLOCK_RUN"]
EvidenceStatus = Literal["NOT_REQUIRED", "PENDING", "COMPLETE", "INCOMPLETE", "FAILED"]
AvailabilityStatus = Literal["ONLINE", "AGENT_OFFLINE", "NOT_FOUND", "CHECKSUM_MISMATCH", "ACCESS_DENIED"]
TASK_VARIABLES_MAX_BYTES = 64 * 1024
TASK_STEPS_MAX_BYTES = 512 * 1024
TASK_BINDINGS_MAX_BYTES = 64 * 1024


class TaskBaseModel(BaseModel):
    """任务接口模型基础类，兼容 ORM 属性并对外使用驼峰字段。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class EvidencePolicyModel(TaskBaseModel):
    """阶段取证策略；只声明约束，不隐式创建截图步骤。"""

    mode: EvidenceMode = "NONE"
    required_types: list[EvidenceType] = Field(default_factory=list)
    required_evidence_keys: list[str] = Field(default_factory=list, max_length=100)
    completeness_policy: EvidenceCompletenessPolicy = "WARN"
    retention_days: int = Field(default=90, ge=1, le=3650)
    mask_profile_id: str = Field(default="", max_length=128)

    @field_validator("required_evidence_keys")
    @classmethod
    def normalize_evidence_keys(cls, value: list[str]) -> list[str]:
        """清理证据键并去重，避免同一缺失项重复展示。"""
        result: list[str] = []
        for item in value or []:
            key = str(item or "").strip()
            if key and key not in result:
                result.append(key)
        return result


class EvidenceMissingModel(TaskBaseModel):
    """阶段或运行缺失的证据项。"""

    evidence_type: EvidenceType | None = None
    evidence_key: str = ""
    reason: str = ""


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
    manual_login_enabled: bool = False
    manual_login_wait_sec: int = Field(default=120, ge=1, le=3600)
    timeout_seconds: int | None = Field(default=None, ge=30, le=21600)
    # 运行级步骤参数覆盖：空值表示沿用步骤自身配置/全局默认。
    default_step_timeout_ms: int | None = Field(default=None, ge=500, le=600000)
    default_step_wait_ms: int | None = Field(default=None, ge=0, le=600000)
    # 步骤参数应用方式：default=作为未单独设置步骤的默认值；force=强制覆盖所有步骤。
    step_param_apply_mode: str = Field(default="default", pattern="^(default|force)$")
    # 执行结束后是否把最终浏览器状态回写到版本绑定的统一凭证（绑定需允许回写）。
    writeback_credential_enabled: bool = False
    # 强制刷新登录态：忽略 Agent 本地缓存的浏览器状态文件，用本次凭证合并的登录态初始化。
    force_refresh_seed_state: bool = False
    # 失败策略：stop=步骤/阶段失败后终止（后续阶段不执行）；continue=继续执行后续步骤与阶段，
    # 失败的阶段照常标记失败，运行终态按是否存在失败判定。
    failure_strategy: str = Field(default="stop", pattern="^(stop|continue)$")

    @field_validator("agent_code", "trigger_type", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        """可选文本去空白，空值按未传处理。"""
        if value is None:
            return None
        return str(value).strip() or None


class TaskRunStopModel(TaskBaseModel):
    """停止或取消运行请求。"""

    reason: str = Field(default="", max_length=200)


class TaskRunDetailModel(TaskBaseModel):
    """任务运行响应；运行ID、任务ID和版本ID按字符串返回。"""

    task_run_id: str
    task_id: str
    task_version_id: str
    version_no: int
    agent_code: str
    trigger_type: str
    status: RunStatus
    business_status: BusinessStatus = "PENDING"
    evidence_status: EvidenceStatus = "NOT_REQUIRED"
    evidence_missing: list[EvidenceMissingModel] = Field(default_factory=list)
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


class StageSplitRuleModel(TaskBaseModel):
    """版本阶段切分规则：优先按稳定步骤 ID 关联，索引仅作兼容字段。"""

    stage_key: str = Field(min_length=1, max_length=128)
    stage_name: str = Field(default="", max_length=255)
    mode: Literal["READ", "PREPARE_WRITE", "WRITE", "VERIFY"] = "READ"
    step_indexes: list[int] = Field(default_factory=list)
    step_ids: list[str] = Field(default_factory=list)
    evidence_policy: EvidencePolicyModel = Field(default_factory=EvidencePolicyModel)
    # 目标系统标识：引用任务系统凭证映射；空表示不使用独立凭证（沿用版本默认绑定）。
    system_key: str = Field(default="", max_length=64)

    @field_validator("stage_key", mode="before")
    @classmethod
    def validate_stage_key(cls, value: str) -> str:
        """阶段标识去空白且不能为空。"""
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("stageKey 不能为空")
        return normalized

    @field_validator("step_indexes")
    @classmethod
    def validate_step_indexes(cls, value: list[int]) -> list[int]:
        """步骤索引必须非负且不重复。"""
        indexes = [int(item) for item in (value or [])]
        if len(set(indexes)) != len(indexes):
            raise ValueError("stepIndexes 不能重复")
        if any(item < 0 for item in indexes):
            raise ValueError("stepIndexes 不能为负数")
        return indexes

    @field_validator("step_ids")
    @classmethod
    def validate_step_ids(cls, value: list[str]) -> list[str]:
        """稳定步骤 ID 去空、去重，兼容旧请求不传。"""
        result: list[str] = []
        for item in value or []:
            step_id = str(item or "").strip()
            if step_id and step_id not in result:
                result.append(step_id)
        return result

    @model_validator(mode="after")
    def validate_stage_steps(self):
        """阶段至少声明一种步骤关联方式。"""
        if not self.step_indexes and not self.step_ids:
            raise ValueError("阶段至少包含一个 stepId 或步骤索引")
        return self


class TaskRunStageModel(TaskBaseModel):
    """运行阶段响应；ID 按字符串返回。"""

    run_stage_id: str
    task_run_id: str
    stage_id: str
    stage_key: str
    stage_name: str
    mode: Literal["READ", "PREPARE_WRITE", "WRITE", "VERIFY"]
    stage_order: int
    step_indexes: list[int] = Field(default_factory=list)
    step_ids: list[str] = Field(default_factory=list)
    evidence_policy: EvidencePolicyModel = Field(default_factory=EvidencePolicyModel)
    evidence_status: EvidenceStatus = "NOT_REQUIRED"
    evidence_missing: list[EvidenceMissingModel] = Field(default_factory=list)
    status: Literal[
        "PENDING",
        "WAITING_APPROVAL",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        "SKIPPED",
        "CANCELLED",
    ]
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str = ""
    error_message: str = ""
    retry_count: int = 0
    approved_by: str = ""
    approved_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class StageApproveModel(TaskBaseModel):
    """WRITE 阶段审批请求；审批意见仅用于审计。"""

    approved: bool
    comment: str = Field(default="", max_length=500)


class ArtifactModel(TaskBaseModel):
    """运行产物响应；ID 和资源 ID 按字符串返回。"""

    artifact_id: str
    task_run_id: str
    run_stage_id: str | None = None
    artifact_type: Literal["step_screenshot", "failure_screenshot", "execution_log", "report"]
    step_key: str = ""
    step_id: str = ""
    evidence_type: EvidenceType | None = None
    evidence_key: str = ""
    sequence_no: int = 1
    captured_at: datetime | None = None
    mask_applied: bool = False
    availability_status: AvailabilityStatus = "ONLINE"
    provider_type: str = "agent_local"
    agent_code: str = ""
    object_key: str = ""
    mime_type: str = ""
    resource_id: str
    original_file_name: str = ""
    file_size: int = 0
    sha256: str = ""
    note: str = ""
    create_time: datetime | None = None


class AgentStepScreenshotModel(TaskBaseModel):
    """Agent 产物上报契约；兼容旧 Base64，metadata-only 事件不携带正文。"""

    task_run_id: str = Field(min_length=1, max_length=64)
    stage_key: str = Field(default="", max_length=128)
    step_id: str = Field(default="", max_length=128)
    step_index: int = Field(default=0, ge=0)
    step_name: str = Field(default="", max_length=255)
    artifact_type: Literal["step_screenshot", "failure_screenshot", "execution_log"] = "step_screenshot"
    evidence_type: EvidenceType | None = None
    evidence_key: str = Field(default="", max_length=255)
    sequence_no: int = Field(default=1, ge=1)
    file_name: str = Field(default="screenshot.png", max_length=255)
    mime_type: str = Field(default="image/png", max_length=128)
    object_key: str = Field(default="", max_length=512)
    provider_type: str = Field(default="agent_local", max_length=32)
    agent_code: str = Field(default="", max_length=128)
    file_size: int | None = Field(default=None, ge=1, le=1024 * 1024 * 1024)
    sha256: str = Field(default="", min_length=0, max_length=64)
    captured_at: datetime | None = None
    mask_applied: bool = False
    data: str | None = Field(default=None, min_length=4, max_length=8 * 1024 * 1024)

    @model_validator(mode="after")
    def normalize_legacy_evidence(self):
        """旧 step_screenshot 映射为 checkpoint_screenshot，并区分元数据与正文事件。"""
        if self.evidence_type is None:
            self.evidence_type = "checkpoint_screenshot" if self.artifact_type == "step_screenshot" else (
                "failure_screenshot" if self.artifact_type == "failure_screenshot" else None
            )
        if self.provider_type != "agent_local" and not self.data:
            raise ValueError("metadata-only 产物只支持 agent_local Provider")
        return self


class RecordingToTemplateModel(TaskBaseModel):
    """录制转模板请求：从录制会话生成任务版本草稿。

    步骤占位符由调用方标记；服务端默认把整个录制转成单一草稿版本，
    fileKey 绑定保持为空，由使用者在版本编辑时补充资源绑定。
    """

    task_id: str = Field(min_length=1, max_length=32)
    recording_id: str = Field(min_length=1, max_length=32)
    version_note: str = Field(default="", max_length=500)
    mark_variables: dict[str, str] = Field(
        default_factory=dict,
        description="步骤索引到变量占位符的映射，如 {\"0\": \"store.id\"}；替换 fill/select 的 value",
    )
    upload_file_keys: dict[int, str] = Field(
        default_factory=dict,
        description="步骤索引到 fileKey 的映射，用于把上传类输入步骤标记为资源引用",
    )

    @field_validator("task_id", "recording_id", mode="before")
    @classmethod
    def validate_id_text(cls, value: str) -> str:
        """ID 必须是数字字符串。"""
        normalized = str(value or "").strip()
        if not normalized.isdigit():
            raise ValueError("ID 必须是数字字符串")
        return normalized


class TaskScheduleModel(TaskBaseModel):
    """定时触发运行配置；cron 使用 5 字段标准表达式（本地时区）。"""

    enabled: bool = False
    cron: str = Field(default="", max_length=64)
    version_no: int | None = Field(default=None, ge=1)
    agent_code: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        """启用时 cron 必填且必须为 5 字段表达式。"""
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        fields = normalized.split()
        if len(fields) != 5:
            raise ValueError("cron 必须是 5 字段表达式：分 时 日 月 周")
        return normalized


class TaskCredentialMappingModel(TaskBaseModel):
    """任务系统凭证映射行：阶段通过 systemKey 声明目标系统。"""

    system_key: str = Field(min_length=1, max_length=64)
    credential_binding_id: str = Field(default="", max_length=64)
    remark: str = Field(default="", max_length=255)

    @field_validator("system_key", "credential_binding_id", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class TaskCredentialMappingSaveModel(TaskBaseModel):
    """批量替换式保存任务的系统凭证映射。"""

    mappings: list[TaskCredentialMappingModel] = Field(default_factory=list, max_length=50)
