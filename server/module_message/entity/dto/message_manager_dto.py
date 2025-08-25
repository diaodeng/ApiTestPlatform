import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from utils.common_util import CamelCaseUtil
from .common_dto import CommonDataModel


class MessageManagerModel(CommonDataModel):
    """
    消息通知配置管理表
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    message_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[int] = None
    desc: Optional[str] = None
    status: Optional[str] = None
    config: Optional[str] = None

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


class MessageManagerModelForApi(MessageManagerModel):
    """
    MessageManagerModel和模块关联表对应pydantic模型
    """
    request_info: TestCase | None = Field(default_factory=lambda: {})

    def request_data(self, request: Any):
        return request


@as_query
@as_form
class MessageManagerPageQueryModel(MessageManagerModel):
    """
    分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class MessageManagerDeleteModel(BaseModel):
    """
    删除API模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    ids: str
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


class FeishuBotConfigModel(BaseModel):
    """
    飞书机器人推送配置模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    title: Optional[str] = None
    content: Optional[str] = None
    footer: Optional[str] = None
