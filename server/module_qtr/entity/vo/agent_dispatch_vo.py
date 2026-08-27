from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AgentAiDispatchRequestModel(BaseModel):
    """
    AI 分析请求分发模型。

    该模型用于 FastAPI 网关接收来自 Worker 的内部派发请求，包含待发送消息体、请求ID和超时参数。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    message: dict[str, Any] = Field(default_factory=dict, description="要转发给 Agent 的完整消息体")
    request_id: str | None = Field(default=None, description="请求ID，留空时由网关自动生成")
    timeout_seconds: int | float | None = Field(default=None, description="请求排队和执行的总超时时间")
