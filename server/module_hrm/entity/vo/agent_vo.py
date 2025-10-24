from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import  Optional
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel


class AgentModel(CommonDataModel):
    """
    Agent表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    agent_id: Optional[int] = None
    agent_name: Optional[str] = None
    agent_code: Optional[str] = None
    online_time: Optional[datetime] = None
    offline_time: Optional[datetime] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[int] = None

@as_query
class AgentQueryModel(QueryModel,AgentModel):
    """
    Agent管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class AgentPageQueryModel(AgentQueryModel):
    """
    定时任务管理分页查询模型
    """
    page_num: int = 1
    page_size: int = 10


class EditJobModel(AgentModel):
    """
    编辑Agent模型
    """
    pass


class DeleteAgentModel(CommonDataModel):
    """
    删除Agent模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    agent_ids: list[str|int]
