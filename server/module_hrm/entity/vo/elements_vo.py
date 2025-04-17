
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel



class ElementsAddModel(CommonDataModel):
    """
    element新增模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    type: Optional[int] = None  # 元素类型：文字，图片等
    name: Optional[str] = None
    value: Optional[str] = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    page_id: Optional[int] = None
    group_id: Optional[int] = None
    notes: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = None
    remark: Optional[str] = None


class ElementsModel(ElementsAddModel):
    """
    elements信息表对应pydantic模型, 用于存数据库前转化数据
    """
    element_id: Optional[int] = None


class ElementsModelForApi(ElementsModel):
    """
    API和模块关联表对应pydantic模型
    """
    pass


class ElementsQueryModel(ElementsModel):
    """
    element不分页查询模型
    """
    pass


@as_query
@as_form
class ElementsPageQueryModel(ElementsQueryModel):
    """
    element分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class DeleteElementsModel(BaseModel):
    """
    删除element模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    element_ids: list[int]
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
