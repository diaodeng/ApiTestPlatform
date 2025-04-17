import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import Field
from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel
from utils.common_util import CamelCaseUtil


class PageRelationAddModel(CommonDataModel):
    """
    page_relation新增模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    page_id: Optional[int] = None
    child_id: Optional[str] = None
    relation_type: Optional[int] = None


class PageRelationModel(PageRelationAddModel):
    """
    page_relation信息表对应pydantic模型, 用于存数据库前转化数据
    """
    relation_id: Optional[int] = None


class PageRelationModelForApi(PageRelationModel):
    """
    API和模块关联表对应pydantic模型
    """
    pass


class PageRelationQueryModel(PageRelationModel):
    """
    page_relation不分页查询模型
    """
    pass


class DeletePageRelationModel(BaseModel):
    """
    删除page_relation模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    page_relation_ids: list[int]
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
