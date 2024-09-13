import json

from pydantic import BaseModel, ConfigDict, Field, field_serializer, root_validator, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Any, Text, Dict
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.entity.vo.common_vo import CommonDataModel
from module_hrm.enums.enums import RunType, DataType
from utils.common_util import CamelCaseUtil


class CaseModel(CommonDataModel):
    """
    主要用于输入入库前的序列化，其他的建议用CaseModelForApi
    用例信息表对应pydantic模型, 用于存数据库前转化数据
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    case_id: Optional[int] = None
    type: Optional[int] = None
    case_name: Optional[str] = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    include: Optional[Any] = None
    request: Optional[Any] = None
    notes: Optional[str] = None
    desc2mind: Optional[str] = None
    sort: Optional[int] = None
    status: Optional[str] = None
    # create_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_by: Optional[str] = None
    # update_time: Optional[datetime] = None
    remark: Optional[str] = None

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('request')
        if isinstance(request_data, str):
            values["request"] = TestCase(**json.loads(request_data))
        elif isinstance(request_data, dict):
            values["request"] = TestCase(**request_data)
        return values

    @field_serializer('request')
    def request_data(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, TestCase):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request

    @field_serializer('include')
    def include_data(self, include: Any):
        if isinstance(include, str):
            return include
        elif isinstance(include, (dict, list)):
            return json.dumps(include, ensure_ascii=False)
        else:
            return include


class CaseRunModel(BaseModel):
    """
    用于用例运行前的序列化
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    ids: Optional[int | List | None] = None
    run_type: Optional[int] = RunType.case.value
    run_model: Optional[int | None] = None
    report_name: Optional[str] = None
    isAsync: Optional[bool] = False
    repeat_num: Optional[int] = 1
    env: int
    case_data: Optional[CaseModel | dict | None] = None


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

    only_self: bool = False


class AddCaseModel(CaseModel):
    """
    新增用例模型
    """
    module_id: Optional[int] = None
    project_id: Optional[int] = None
    type: Optional[str | int] = DataType.case.value


class DeleteCaseModel(BaseModel):
    """
    删除用例模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    case_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
