from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query


class EnvModel(BaseModel):
    """
    环境表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    env_id: Optional[int] = None
    env_name: Optional[str] = None
    env_url: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[str] = None
    del_flag: Optional[str] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


@as_query
class EnvQueryModel(EnvModel):
    """
    环境管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class DeleteEnvModel(BaseModel):
    """
    删除环境模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    env_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
