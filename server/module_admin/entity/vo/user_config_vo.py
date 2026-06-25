from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class UserConfigModel(BaseModel):
    """
    用户配置模型，用于接口保存和返回当前登录用户的配置项。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    config_id: int | None = Field(default=None, description="配置主键")
    user_id: int | None = Field(default=None, description="用户ID")
    config_type: str = Field(description="配置类型，用于隔离功能域，如 ticket")
    config_key: str = Field(description="配置键名，用于区分同一类型下的具体配置")
    config_value: dict[str, Any] | list[Any] | str | int | float | bool | None = Field(
        default=None,
        description="配置值，建议使用JSON对象保存页面偏好",
    )
    remark: str | None = Field(default=None, description="配置说明")
    create_by: str | None = Field(default=None, description="创建者")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_by: str | None = Field(default=None, description="更新者")
    update_time: datetime | None = Field(default=None, description="更新时间")
