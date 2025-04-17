import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import Field
from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel
from utils.common_util import CamelCaseUtil


class FunctionRelationAddModel(CommonDataModel):
    """
    function_relation新增模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    function_id: Optional[int] = None
    child_id: Optional[str] = None
    sort: Optional[int] = None


class FunctionRelationModel(FunctionRelationAddModel):
    """
    function_relation信息表对应pydantic模型, 用于存数据库前转化数据
    """
    relation_id: Optional[int] = None


class FunctionRelationModelForApi(FunctionRelationModel):
    """
    API和模块关联表对应pydantic模型
    """
    pass


class FunctionRelationQueryModel(FunctionRelationModel):
    """
    function_relation不分页查询模型
    """
    pass


@as_query
@as_form
class FunctionRelationPageQueryModel(FunctionRelationQueryModel):
    """
    function_relation分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class DeleteFunctionRelationModel(BaseModel):
    """
    删除function_relation模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    function_relation_ids: list[int]
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
