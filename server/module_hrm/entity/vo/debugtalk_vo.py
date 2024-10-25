from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel


class DebugTalkModel(CommonDataModel):
    """
    DebugTalk表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    debugtalk_id: Optional[int] = None
    project_id: Optional[int] = None
    debugtalk: Optional[str] = None
    status: Optional[str] = None
    del_flag: Optional[str] = None
    # create_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_by: Optional[str] = None
    # update_time: Optional[datetime] = None


@as_query
class DebugTalkQueryModel(QueryModel, DebugTalkModel):
    """
    DebugTalk管理不分页查询模型
    """
    project_id: Optional[int] = None
    status: Optional[str] = None


class DeleteDebugTalkModel(BaseModel):
    """
    删除DebugTalk模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    project_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
