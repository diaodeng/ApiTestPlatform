from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel


class ConfigDataModel(BaseModel):
    """
    配置数据模型
    """
    key: Optional[str]
    type: Optional[str] = "Any"
    value: Optional[str | bool | int | float] = None
    desc: Optional[str] = None
    enable: Optional[bool] = None


class CrudResponseModel(BaseModel):
    """
    操作响应模型
    """
    is_success: bool
    message: str
    result: Optional[Any] = None


class UploadResponseModel(BaseModel):
    """
    上传响应模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    file_name: Optional[str] = None
    new_file_name: Optional[str] = None
    original_filename: Optional[str] = None
    url: Optional[str] = None


class QueryModel(BaseModel):
    """
    通用查询模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    page_num: int = 1
    page_size: int = 10
    begin_time: Optional[Any] = None
    end_time: Optional[Any] = None
    status: Optional[Any] = None
    id: Optional[Any] = None
    only_self: bool = False
    is_page: bool = True

    @model_validator(mode="before")
    @classmethod
    def normalize_query_numbers(cls, data):
        """
        归一化查询参数中的分页与ID字段，兼容空字符串和字符串数字。
        :param data: 原始查询参数
        :return: 归一化后的查询参数
        """
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        for key in ("pageNum", "page_size", "pageSize", "id"):
            value = normalized.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    normalized[key] = None
                    continue
                if text.isdigit():
                    normalized[key] = int(text)
        return normalized


class CommonDataModel(BaseModel):
    """
    通用数据模型（包含数据库对应的通用字段）
    """
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True,
                              populate_by_name=True
                              )
    id: int | None = None
    dept_id: int | None = None
    create_by: Optional[str | Any] = None
    update_by: Optional[str | Any] = None
    create_time: Optional[str | Any] = None
    update_time: Optional[str | Any] = None
    manager: Optional[int] = None
