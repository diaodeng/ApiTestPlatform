import json
from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator, Field
from pydantic.alias_generators import to_camel

from utils.common_util import CamelCaseUtil
from .common_dto import CommonDataModel
from ...enums.enums import PushConfigTypeEnum, PushWayEnum, QtrDataStatusEnum


class MessageConfigModel(CommonDataModel):
    """
    消息通知配置内容
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    config_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    footer: Optional[str] = None


class MessageManagerModel(CommonDataModel):
    """
    消息通知配置管理表
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    message_id: Optional[int] = None
    name: Optional[str] = None
    push_way: Optional[int] = PushWayEnum.FEISHU_BOT.value
    desc: Optional[str] = None
    status: Optional[str] = QtrDataStatusEnum.normal.value
    config_type: Optional[int] = PushConfigTypeEnum.TEMPLATE.value
    config: Optional[Any] = None

    # create_by: Optional[str] = None
    # update_by: Optional[str] = None
    # create_time: Optional[datetime] = None
    # update_time: Optional[datetime] = None
    # manager: Optional[int] = None

    @model_validator(mode="before")
    def convert_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        config_data = values.get('config')
        if isinstance(config_data, str):
            values["config"] = MessageConfigModel(**json.loads(config_data))
        elif isinstance(config_data, dict):
            values["config"] = MessageConfigModel(**config_data)
        return values

    @field_serializer('config')
    def config_data_handle(self, configs: Any):
        if isinstance(configs, str):
            return configs
        elif isinstance(configs, (dict, list)):
            return json.dumps(configs, ensure_ascii=False)
        elif isinstance(configs, MessageConfigModel):
            return configs.model_dump_json(by_alias=True, exclude_unset=True)
        else:
            return configs


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
