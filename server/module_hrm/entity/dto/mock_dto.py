import json
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import RunTypeEnum, DataType
from utils.common_util import CamelCaseUtil


class MockConditionModel(BaseModel):
    source: str = 'query'  # query\body\header
    key: Optional[str] = ''
    operator: Optional[str] = '='
    value: Optional[Any] = ''
    data_type: str = 'str'  # str\num\float


class MockModel(CommonDataModel):
    """
    mock数据的数据处理模型，内部数据交换使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    rule_id: int | str | None = None
    project_id: Optional[int] = None
    module_id: Optional[int] = None
    parent_id: Optional[int] = None
    type: Optional[int] = None
    mock_type: Optional[int] = None
    rule_tag: Optional[str] = None

    name: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    priority: Optional[int] = None
    rule_condition: Optional[list[MockConditionModel]] = Field(default_factory=lambda: [])
    status: Optional[int] = None  # QtrDataStatusEnum.normal.value
    desc: Optional[str] = None

    @model_validator(mode="before")
    def convert_condition(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('ruleCondition')
        if not request_data:
            return values
        if isinstance(request_data, str):
            values["ruleCondition"] = [MockConditionModel(**condition) for condition in json.loads(request_data)]
        elif isinstance(request_data, list):
            values["ruleCondition"] = [MockConditionModel(**condition) for condition in request_data]
        return values


class MockModelForDb(MockModel):
    """
    mock数据入库使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    @field_serializer('rule_condition')
    def serializer_rule_condition(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, MockConditionModel):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request



class MockRequestModel(CommonDataModel):
    """
    mock请求数据的数据处理模型，内部数据交换使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    rule_request_id: int | str | None = None
    name: Optional[str] = None
    request_tag: Optional[str] = None
    is_default: Optional[int] = None
    status: Optional[int] = None  # QtrDataStatusEnum.normal.value
    priority: Optional[int] = None
    request_condition: Optional[list[MockConditionModel]] = Field(default_factory=lambda: [])
    rule_id: int | str | None = None

    headers_template: Optional[str] = None
    body_template: Optional[str] = None
    query_template: Optional[str] = None
    desc: Optional[str] = None

    @model_validator(mode="before")
    def convert_condition(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('requestCondition')
        if not request_data:
            return values
        if isinstance(request_data, str):
            values["requestCondition"] = [MockConditionModel(**condition) for condition in json.loads(request_data)]
        elif isinstance(request_data, list):
            values["requestCondition"] = [MockConditionModel(**condition) for condition in request_data]
        return values


class MockRequestModelForDb(MockRequestModel):
    """
    mock请求数据入库使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    @field_serializer('request_condition')
    def request_condition(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, MockConditionModel):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request



class MockResponseModel(CommonDataModel):
    """
    mock响应数据的数据处理模型，内部数据交换使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    rule_response_id: int | str | None = None
    name: Optional[str] = None
    response_tag: Optional[str] = None
    is_default: Optional[int] = None
    status: Optional[int] = None  # QtrDataStatusEnum.normal.value
    priority: Optional[int] = None
    response_condition: Optional[list[MockConditionModel]] = Field(default_factory=lambda: [])
    rule_id: int | str | None = None
    status_code: int = None

    headers_template: Optional[str] = None
    body_template: Optional[str] = None
    delay: Optional[int] = None
    desc: Optional[str] = None

    @model_validator(mode="before")
    def convert_condition(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('responseCondition')
        if not request_data:
            return values
        if isinstance(request_data, str):
            values["responseCondition"] = [MockConditionModel(**condition) for condition in json.loads(request_data)]
        elif isinstance(request_data, list):
            values["responseCondition"] = [MockConditionModel(**condition) for condition in request_data]
        return values


class MockResponseModelForDb(MockResponseModel):
    """
    mock响应数据入库使用
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    @field_serializer('response_condition')
    def request_data(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, MockConditionModel):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request
