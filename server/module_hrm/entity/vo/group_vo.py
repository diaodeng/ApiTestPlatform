
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel



class GroupAddModel(CommonDataModel):
    """
    group新增模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    name: Optional[str] = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    page_id: Optional[int] = None
    group_type: Optional[int] = None
    notes: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = None
    remark: Optional[str] = None


class GroupModel(GroupAddModel):
    """
    group信息表对应pydantic模型, 用于存数据库前转化数据
    """
    group_id: Optional[int] = None


class GroupModelForApi(GroupModel):
    """
    API和模块关联表对应pydantic模型
    """
    pass


class GroupQueryModel(GroupModel):
    """
    group不分页查询模型
    """
    pass


@as_query
@as_form
class GroupPageQueryModel(GroupQueryModel):
    """
    group分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class DeleteGroupModel(BaseModel):
    """
    删除group模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    group_ids: list[int]
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
