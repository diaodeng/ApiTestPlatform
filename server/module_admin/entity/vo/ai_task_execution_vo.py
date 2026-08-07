from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel
from pydantic.alias_generators import to_camel


class AiTaskExecutionBaseModel(BaseModel):
    """
    AI 任务执行审计基础模型。
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        from_attributes=True,
        populate_by_name=True,
        protected_namespaces=(),
    )

    execution_id: int | None = None
    task_type: str | None = Field(default=None, description="任务类型编码")
    task_name: str | None = Field(default=None, description="任务名称")
    source_type: str | None = Field(default=None, description="来源类型")
    source_id: int | None = Field(default=None, description="来源ID")
    source_ref: str | None = Field(default=None, description="来源引用")
    provider_code: str | None = Field(default=None, description="Provider编码")
    prompt_code: str | None = Field(default=None, description="提示词编码")
    model_name: str | None = Field(default=None, description="模型名称")
    base_url: str | None = Field(default=None, description="调用地址")
    status: str | None = Field(default=None, description="执行状态")
    request_payload: dict[str, Any] | list[Any] | str | None = Field(default=None, description="请求载荷")
    response_payload: dict[str, Any] | list[Any] | str | None = Field(default=None, description="响应载荷")
    response_text: str | None = Field(default=None, description="原始响应文本")
    token_usage: dict[str, Any] | None = Field(default=None, description="Token用量")
    error_message: str | None = Field(default=None, description="错误信息")
    created_by_id: int | None = Field(default=None, description="创建人ID")
    created_by_name: str | None = Field(default=None, description="创建人名称")
    create_time: datetime | None = None
    update_time: datetime | None = None


@as_query
class AiTaskExecutionQueryModel(QueryModel):
    """
    AI 任务执行审计查询模型。
    """

    task_type: str | None = Field(default=None, description="任务类型编码")
    source_type: str | None = Field(default=None, description="来源类型")
    source_ref: str | None = Field(default=None, description="来源引用")
    provider_code: str | None = Field(default=None, description="Provider编码")
    status: str | None = Field(default=None, description="执行状态")
    keyword: str | None = Field(default=None, description="关键字，匹配任务名、来源和错误信息")


class AiTaskExecutionDetailModel(AiTaskExecutionBaseModel):
    """
    AI 任务执行审计详情模型。
    """

    pass
