import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel
from module_hrm.enums.enums import PushReminderEnum
from utils.common_util import CamelCaseUtil


class FeishuRobotModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True,
                              populate_by_name=True)
    url: Optional[str] = None
    secret: Optional[str] = None
    content: Optional[str] = None
    keywords: Optional[list] = Field(default_factory=lambda: [])
    at_user_id: Optional[list] = Field(default_factory=lambda: [])
    push: bool = False
    at_reminder: int = Field(default_factory=lambda: PushReminderEnum.no_reminder.value)

class AllPushModel(CommonDataModel):
    """
    所有推送数据模型
    """

    push_id: Optional[int] = None
    type: Optional[int] = None
    allow_push: Optional[int] = None
    name: Optional[str] = None


class PushModel(CommonDataModel):
    """
    推送数据模型
    """
    model_config = ConfigDict(alias_generator=to_camel,
                              from_attributes=True)

    push_id: Optional[int|str] = None
    type: Optional[int] = None
    allow_push: Optional[int] = None
    name: Optional[str] = None
    config_content: Optional[dict|str|None] = None
    desc: Optional[str] = None

    def data_to_db(self):
        if isinstance(self.config_content, (dict, list)):
            self.config_content = json.dumps(self.config_content, ensure_ascii=False)
        return self.model_dump(exclude_unset=True)


    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        config_data = values.get('configContent')
        if isinstance(config_data, str):
            values["configContent"] = json.loads(config_data) if config_data else None

        return values

    # @field_serializer('config_content')
    # def request_data(self, request: Any):
    #     if isinstance(request, (dict, list)):
    #         return request
    #     elif isinstance(request, str):
    #         return json.loads(request)
    #     else:
    #         return request


@as_query
@as_form
class PushPageQueryModel(CommonDataModel):
    """
    API分页查询模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    push_id: Optional[int] = None
    type: Optional[int] = None
    allow_push: Optional[int] = None
    name: Optional[str] = None
    desc: Optional[str] = None

    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class DeletePushModel(BaseModel):
    """
    删除API模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    push_ids: list = Field(default_factory=lambda: [])
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
