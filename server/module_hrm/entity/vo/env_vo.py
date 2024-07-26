import json

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Dict, Text, Any
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query
from utils.common_util import CamelCaseUtil


class EnvConfig(BaseModel):
    """
    环境配置模型
    """
    variables: Optional[Dict[Text, List[Dict]]] = {"default": []}


class EnvModel(BaseModel):
    """
    环境表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    env_id: Optional[int] = None
    env_name: Optional[str] = None
    env_url: Optional[str] = None
    env_config: Optional[Any] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[str] = None
    del_flag: Optional[str] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        env_config = values.get('envConfig')
        if isinstance(env_config, str):
            values["envConfig"] = EnvConfig(**json.loads(env_config))
        elif isinstance(env_config, dict):
            values["envConfig"] = EnvConfig(**env_config)
        return values

    @field_serializer('env_config')
    def env_config_data(self, env_config: EnvConfig):
        if not env_config:
            return '{}'
        if isinstance(env_config, str):
            return env_config
        if isinstance(env_config, (dict, list)):
            return json.dumps(env_config, ensure_ascii=False)

        return env_config.model_dump_json(by_alias=True, exclude_unset=True)


class EnvModelForApi(EnvModel):
    """
    环境列表模型
    """

    env_config: Optional[EnvConfig | Any] = EnvConfig()

    def env_config_data(self, env_config):
        if not env_config:
            return EnvConfig().model_dump()
        return env_config.model_dump()


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
