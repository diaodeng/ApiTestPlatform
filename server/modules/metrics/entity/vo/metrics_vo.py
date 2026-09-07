"""资源采集服务对外接口模型，所有接口契约使用 Pydantic 定义和校验。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


class MetricsCollectorBaseModel(BaseModel):
    """采集服务接口模型基础类，统一驼峰别名。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)


class MetricsCollectorSaveModel(MetricsCollectorBaseModel):
    """新增或修改采集服务的请求体。password 仅写入时接收，响应永不回显。"""

    profile_name: str = Field(min_length=1, max_length=64)
    enabled: bool = False
    push_url: str = Field(default="", max_length=255)
    auth_user: str = Field(default="", max_length=64)
    # 认证密码明文，仅写入时接收；为空表示不修改旧密码
    auth_password: str = Field(default="", max_length=128)
    job_label: str = Field(default="QTR", max_length=64)
    instance_label: str = Field(default="TEST_ENV", max_length=64)
    machine_label: str = Field(default="", max_length=64)
    interval_seconds: int = Field(default=5, ge=1, le=3600, description="推送间隔秒数，下限1秒防止打爆接收端")
    batch_size: int = Field(default=100, ge=1, le=10000, description="单批最大样本条数")
    timeout_seconds: int = Field(default=10, ge=1, le=60, description="推送请求超时秒数")
    extended_enabled: bool = False
    remark: str | None = None

    @field_validator("push_url", mode="before")
    @classmethod
    def validate_push_url(cls, value):
        """推送地址启用时必须填写，且只接受 http/https 协议。"""
        url = str(value or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            raise ValueError("推送地址必须以 http:// 或 https:// 开头")
        return url


class MetricsCollectorStatusModel(MetricsCollectorBaseModel):
    """启停采集服务的请求体。"""

    enabled: bool


class MetricsCollectorQueryModel(MetricsCollectorBaseModel):
    """采集服务列表查询参数。"""

    model_config = ConfigDict(alias_generator=to_camel)

    page_num: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


MetricsCollectorQueryModel = as_query(MetricsCollectorQueryModel)


class MetricsCollectorResponseModel(MetricsCollectorBaseModel):
    """采集服务列表/详情响应体，密码只返回是否存在标记。"""

    profile_id: int
    profile_name: str
    enabled: bool
    push_url: str
    auth_user: str
    auth_password_set: bool = False
    job_label: str
    instance_label: str
    machine_label: str
    interval_seconds: int
    batch_size: int
    timeout_seconds: int
    extended_enabled: bool
    revision: int
    last_push_time: datetime | None = None
    last_push_status: str = "never"
    last_push_message: str = ""
    push_failure_count: int = 0
    remark: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class MetricsCollectorRuntimeProcessModel(MetricsCollectorBaseModel):
    """单个进程角色的采集运行状态。"""

    role: str
    pid: int
    running: bool
    active_profile_ids: list[int] = Field(default_factory=list)
    last_poll_time: str | None = None
    last_error: str = ""


class MetricsCollectorRuntimeResponseModel(MetricsCollectorBaseModel):
    """采集运行时状态响应体：按进程角色汇总。"""

    processes: list[MetricsCollectorRuntimeProcessModel] = Field(default_factory=list)


class MemorySnapshotConfigModel(MetricsCollectorBaseModel):
    """内存诊断快照配置的请求/响应体。"""

    enabled: bool = Field(default=False, description="总开关，开启后采集线程每10秒检查一次进程RSS")
    rss_threshold_mb: int = Field(default=900, ge=128, le=65536, description="触发阈值（MB）")
    top_lines: int = Field(default=50, ge=10, le=500, description="快照记录的top分配源条数")
    cooldown_seconds: int = Field(default=3600, ge=60, le=86400, description="两次采样之间的冷却秒数")
    update_time: datetime | None = None
    update_by: str | None = None
