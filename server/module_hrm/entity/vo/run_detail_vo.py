import json

from pydantic import BaseModel, ConfigDict, Field, field_serializer, root_validator, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Any, Text, Dict

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel, CommonDataModel
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase
from module_hrm.enums.enums import CaseRunStatus
from utils.common_util import CamelCaseUtil


class RunDetailDelModel(BaseModel):
    """
    报告删除模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    detail_ids: Optional[List[Text | int]] = []


class HrmRunListModel(CommonDataModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    detail_id: Optional[int] = None
    run_id: Optional[int] = None
    report_id: Optional[int] = None
    run_name: Optional[Text] = None
    run_type: Optional[int] = None
    run_start_time: Any = None
    run_end_time: Any = None
    run_duration: float = 0
    status: Optional[int] = CaseRunStatus.passed.value
    # id: int
    # create_by: Text | None = None
    # update_by: Text | None = None
    # create_time: Any = None
    # update_time: Any = None


@as_query
class RunDetailQueryModel(QueryModel, HrmRunListModel):
    """
    报告查询模型
    """
    run_id: Any = None
    run_type: Any = None
    report_id: Any = None
    run_name: Text | None = None


class HrmRunDetailModel(HrmRunListModel):
    """
    报告模型
    """
    run_detail: TestCase | Text | None = None

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('runDetail')
        if isinstance(request_data, str):
            values["runDetail"] = TestCase(**json.loads(request_data))
        elif isinstance(request_data, dict):
            values["runDetail"] = TestCase(**request_data)
        return values
