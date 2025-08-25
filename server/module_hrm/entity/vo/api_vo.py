import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.entity.vo.common_vo import CommonDataModel
from utils.common_util import CamelCaseUtil


class ApiModel(CommonDataModel):
    """
    API接口信息表对应pydantic模型, 用于存数据库前转化数据
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    api_id: Optional[int] = None
    type: Optional[int] = None
    api_type: Optional[int] = None
    name: Optional[str] = None
    path: Optional[str] = None
    interface: Optional[str] = None
    parent_id: Optional[int] = None
    author: Optional[str] = None
    request_info: Optional[Any] = None
    request_data_demo: Optional[str] = None
    response_data_demo: Optional[str] = None
    desc: Optional[str] = None
    id: Optional[int] = None

    # create_by: Optional[str] = None
    # update_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_time: Optional[datetime] = None
    # manager: Optional[int] = None

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        request_data = values.get('requestInfo')
        if isinstance(request_data, str):
            values["requestInfo"] = TestCase(**json.loads(request_data))
        elif isinstance(request_data, dict):
            values["requestInfo"] = TestCase(**request_data)
        return values

    @field_serializer('request_info')
    def request_data(self, request: Any):
        if isinstance(request, str):
            return request
        elif isinstance(request, (dict, list)):
            return json.dumps(request, ensure_ascii=False)
        elif isinstance(request, TestCase):
            return request.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return request


class ApiModelForApi(ApiModel):
    """
    API和模块关联表对应pydantic模型
    """
    request_info: TestCase | None = Field(default_factory=lambda: {})

    def request_data(self, request: Any):
        return request


class ApiQueryModel(ApiModel):
    """
    API不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None
    private: Optional[bool] = False


@as_query
@as_form
class ApiPageQueryModel(ApiQueryModel):
    """
    API分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    module_id: Optional[int] = None
    project_id: Optional[int] = None
    only_self: Optional[bool] = False


class DeleteApiModel(BaseModel):
    """
    删除API模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    case_ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
