from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import QtrDataStatusEnum


class ProjectModel(CommonDataModel):
    """
    项目表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    project_id: Optional[int] = None
    project_name: Optional[str] = None
    responsible_name: Optional[str] = None
    test_user: Optional[str] = None
    dev_user: Optional[str] = None
    publish_app: Optional[str] = None
    simple_desc: Optional[str] = None
    other_desc: Optional[str] = None
    order_num: Optional[int] = None
    status: Optional[int] = QtrDataStatusEnum.normal.value
    del_flag: Optional[str] = None
    # create_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_by: Optional[str] = None
    # update_time: Optional[datetime] = None


@as_query
class ProjectQueryModel(QueryModel, ProjectModel):
    """
    项目管理不分页查询模型
    """
    pass


class DeleteProjectModel(BaseModel):
    """
    删除项目模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    project_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
