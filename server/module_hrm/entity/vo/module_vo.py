from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import QtrDataStatusEnum


class ModuleModel(CommonDataModel):
    """
    模块信息表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    module_id: Optional[int] = None
    project_id: Optional[int] = None
    module_name: Optional[str] = None
    test_user: Optional[str] = None
    simple_desc: Optional[str] = None
    other_desc: Optional[str] = None
    desc2mind: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[int] = QtrDataStatusEnum.normal.value
    # create_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_by: Optional[str] = None
    # update_time: Optional[datetime] = None
    remark: Optional[str] = None


class ModuleProjectModel(BaseModel):
    """
    模块和项目关联表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    module_id: Optional[int] = None
    project_id: Optional[int] = None


class ModuleQueryModel(ModuleModel):
    """
    模块管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None
    project_id: Optional[int] = None


class ModuleQuery(ModuleModel):
    """
    模块查询
    """
    project_id: Optional[int] = None


@as_query
@as_form
class ModulePageQueryModel(QueryModel, ModuleQueryModel):
    """
    模块管理分页查询模型
    """
    pass


class AddModuleModel(ModuleModel):
    """
    新增模块模型
    """
    project_id: Optional[int] = None
    type: Optional[str] = None


class DeleteModuleModel(BaseModel):
    """
    删除模块模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    module_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
