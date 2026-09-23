"""Agent 受控上传目录文件查询契约，供编辑器"Agent 目录文件"模式选择。

只暴露受控相对路径与元数据，不接收、不返回绝对路径和文件内容。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


@as_query
class AgentUploadFileQueryModel(BaseModel):
    """Agent 受控上传目录列表查询参数。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    agent_code: str = Field(min_length=1, max_length=128)
    prefix: str = Field(default="", max_length=512)

    @field_validator("agent_code", mode="before")
    @classmethod
    def normalize_agent_code(cls, value):
        """统一查询文本空白，空字符串按未传处理。"""
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("prefix", mode="before")
    @classmethod
    def normalize_prefix(cls, value):
        """prefix 未传时 as_query 会给 None，必须按空串处理，否则 str 校验失败。"""
        if value is None:
            return ""
        normalized = str(value).strip()
        return normalized


class AgentUploadFileEntryModel(BaseModel):
    """受控上传目录条目：相对路径 + 类型 + 大小 + 修改时间戳。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    path: str = Field(min_length=1, max_length=512)
    type: Literal["file", "directory"]
    size: int = Field(default=0, ge=0)
    modified_at: int = Field(default=0, ge=0)
