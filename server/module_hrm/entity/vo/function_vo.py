import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import Field
from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel
from utils.common_util import CamelCaseUtil


class FunctionAddModel(CommonDataModel):
    """
    function新增模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    type: Optional[int] = None
    name: Optional[str] = None
    info: Optional[dict] = Field(default_factory=lambda: {})
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    group_id: Optional[int] = None
    notes: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = None
    remark: Optional[str] = None


class FunctionModel(FunctionAddModel):
    """
    function信息表对应pydantic模型, 用于存数据库前转化数据
    """
    function_id: Optional[int] = None


class FunctionModelForApi(FunctionModel):
    """
    API和模块关联表对应pydantic模型
    """
    pass


class FunctionQueryModel(FunctionModel):
    """
    function不分页查询模型
    """
    pass


@as_query
@as_form
class FunctionPageQueryModel(FunctionQueryModel):
    """
    function分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class DeleteFunctionModel(BaseModel):
    """
    删除function模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    function_ids: list[int]
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
