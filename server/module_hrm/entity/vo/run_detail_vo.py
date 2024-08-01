import json

from pydantic import BaseModel, ConfigDict, Field, field_serializer, root_validator, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Any, Text, Dict

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


@as_query
class RunDetailQueryModel(QueryModel):
    """
    报告查询模型
    """
    run_id: Any = None
    run_type: Any = None
    report_id: int | Any = None


class RunDetailDelModel(BaseModel):
    """
    报告删除模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    detail_ids: Optional[List[Text | int]] = []


class HrmRunListModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    detail_id: int
    run_id: Optional[int] = None
    report_idL: Optional[int] = None
    run_name: Text
    run_type: int
    run_start_time: Any = None
    run_end_time: Any = None
    run_duration: float = 0
    status: int
    id: int
    create_by: Text | None = None
    update_by: Text | None = None
    create_time: Any = None
    update_time: Any = None


class HrmRunDetailModel(HrmRunListModel):
    """
    报告模型
    """
    run_detail: Text = None
