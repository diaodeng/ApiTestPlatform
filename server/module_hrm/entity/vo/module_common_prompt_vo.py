from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class ModuleCommonPromptBaseModel(BaseModel):
    """
    模块通用提示词基础请求模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    module_code: str = Field(min_length=1, max_length=128)
    prompt_content: str = Field(min_length=1)
    enabled: bool = True
    remark: Optional[str] = Field(default="", max_length=500)

    @field_validator("module_code", "prompt_content", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """
        归一化编码和正文，避免首尾空白造成重复配置或空内容。
        """
        return str(value or "").strip()

    @field_validator("remark", mode="before")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str:
        """
        归一化备注文本。
        """
        return str(value or "").strip()


class CreateModuleCommonPromptModel(ModuleCommonPromptBaseModel):
    """新增模块通用提示词请求模型。"""


class UpdateModuleCommonPromptModel(BaseModel):
    """修改模块通用提示词请求模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    prompt_id: int
    prompt_content: str = Field(min_length=1)
    enabled: bool = True
    remark: Optional[str] = Field(default="", max_length=500)

    @field_validator("prompt_content", mode="before")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """归一化提示词正文。"""
        return str(value or "").strip()

    @field_validator("remark", mode="before")
    @classmethod
    def normalize_remark(cls, value: str | None) -> str:
        """归一化备注文本。"""
        return str(value or "").strip()


@as_query
class ModuleCommonPromptPageQueryModel(QueryModel):
    """模块通用提示词分页查询模型。"""

    keyword: Optional[str] = None
    module_code: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("keyword", "module_code", mode="before")
    @classmethod
    def normalize_query_text(cls, value: str | None) -> str | None:
        """归一化查询条件。"""
        text = str(value or "").strip()
        return text or None


class ModuleCommonPromptOptionModel(BaseModel):
    """模块编码下拉选项模型。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    module_code: str
    module_count: int = 0
    project_count: int = 0


class ModuleCommonPromptModel(ModuleCommonPromptBaseModel):
    """模块通用提示词返回模型。"""

    prompt_id: int
    module_count: int = 0
    project_count: int = 0
    create_time: Optional[Any] = None
    update_time: Optional[Any] = None

    @field_serializer("prompt_id")
    def serialize_prompt_id(self, value: int) -> str:
        """将可能超出 JavaScript 安全整数范围的主键序列化为字符串。"""
        return str(value)
