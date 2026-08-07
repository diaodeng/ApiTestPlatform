from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


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

    analysis_worker_command: str | None = Field(default=None, description="分析Worker命令")
    analysis_worker_model: str | None = Field(default=None, description="分析Worker模型")
    analysis_worker_sandbox: str | None = Field(default=None, description="分析Worker沙箱")
    analysis_worker_timeout_sec: int | None = Field(default=None, description="分析Worker超时秒数")
    analysis_workspace_root: str | None = Field(default=None, description="分析工作区根目录")
    analysis_agent_code: str | None = Field(default=None, description="分析Agent编码")
    analysis_log_mode: str | None = Field(default=None, description="分析日志模式")
    analysis_log_window_missing_strategy: str | None = Field(default=None, description="日志时间窗口缺失策略")
    config_rows: list[AiConfigSummaryItemModel] = Field(default_factory=list, description="配置明细")
    quick_links: list[dict[str, Any]] = Field(default_factory=list, description="快捷入口")


class AiConfigUpdateModel(BaseModel):
    """
    AI 聚合配置更新模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    analysis_worker_command: str | None = Field(default=None, description="分析Worker命令")
    analysis_worker_model: str | None = Field(default=None, description="分析Worker模型")
    analysis_worker_sandbox: str | None = Field(default=None, description="分析Worker沙箱")
    analysis_worker_timeout_sec: int | None = Field(default=None, description="分析Worker超时秒数")
    analysis_workspace_root: str | None = Field(default=None, description="分析工作区根目录")
    analysis_agent_code: str | None = Field(default=None, description="分析Agent编码")
    analysis_log_mode: str | None = Field(default=None, description="分析日志模式")
    analysis_log_window_missing_strategy: str | None = Field(default=None, description="日志时间窗口缺失策略")
