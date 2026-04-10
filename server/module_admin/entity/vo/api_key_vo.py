from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


class ApiKeyModel(BaseModel):
    """
    API Key信息响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    api_key_id: Optional[int] = None
    user_id: Optional[int] = None
    key_name: Optional[str] = None
    key_code: Optional[str] = None
    key_prefix: Optional[str] = None
    permission_codes: list[str] = Field(default_factory=list)
    expire_time: Optional[datetime] = None
    never_expire: Optional[bool] = False
    status: Optional[str] = None
    last_used_ip: Optional[str] = None
    last_used_time: Optional[datetime] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None
    remark: Optional[str] = None
    is_expired: Optional[bool] = False
    expire_reason: Optional[str] = None


class ApiKeyQueryModel(BaseModel):
    """
    API Key查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    key_name: Optional[str] = None


@as_query
class ApiKeyPageQueryModel(ApiKeyQueryModel):
    """
    API Key分页查询模型
    """

    page_num: int = 1
    page_size: int = 10


class CreateApiKeyModel(BaseModel):
    """
    新增API Key请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    key_name: str
    permission_codes: list[str] = Field(default_factory=list)
    expire_time: Optional[datetime] = None
    never_expire: Optional[bool] = False
    remark: Optional[str] = None


class ViewApiKeyModel(BaseModel):
    """
    查看API Key请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    user_name: str
    password: str


class ApiKeySecretModel(BaseModel):
    """
    API Key明文响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    api_key_id: Optional[int] = None
    key_name: Optional[str] = None
    api_key: str


class ApiKeyPermissionOptionModel(BaseModel):
    """
    API Key权限选项响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    perm: str
    name: str
    menu_type: Optional[str] = None
    parent_name: Optional[str] = None
