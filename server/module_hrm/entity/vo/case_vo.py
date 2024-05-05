from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query, as_form


class CaseModel(BaseModel):
    """
    用例信息表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    case_id: Optional[int] = None
    type: Optional[int] = None
    case_name: Optional[str] = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    include: Optional[str] = None
    request: Optional[str] = None
    notes: Optional[str] = None
    desc2mind: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[str] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
    remark: Optional[str] = None


class CaseModuleProjectModel(BaseModel):
    """
    用例和用例和项目关联表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    case_id: Optional[int] = None
    module_id: Optional[int] = None
    project_id: Optional[int] = None


class CaseQueryModel(CaseModel):
    """
    用例管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class CaseQuery(CaseModel):
    """
    用例查询
    """
    module_id: Optional[int] = None
    project_id: Optional[int] = None


@as_query
@as_form
class CasePageQueryModel(CaseQueryModel):
    """
    用例管理分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    module_id: Optional[int] = None
    project_id: Optional[int] = None


class AddCaseModel(CaseModel):
    """
    新增用例模型
    """
    module_id: Optional[int] = None
    project_id: Optional[int] = None
    type: Optional[str] = None


class DeleteCaseModel(BaseModel):
    """
    删除用例模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    case_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
