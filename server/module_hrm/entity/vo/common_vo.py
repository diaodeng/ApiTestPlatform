from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional, Any


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
    only_self:bool = False


class CommonDataModel(BaseModel):
    """
    通用数据模型（包含数据库对应的通用字段）
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    id: int | None = None
    create_by: Optional[str | Any] = None
    update_by: Optional[str | Any] = None
    create_time: Optional[str | Any] = None
    update_time: Optional[str | Any] = None
    manager: Optional[int] = None
