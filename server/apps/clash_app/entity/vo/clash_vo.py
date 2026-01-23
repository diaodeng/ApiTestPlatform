from typing import Optional

from pydantic import ConfigDict, BaseModel
from pydantic.alias_generators import to_camel

from module_hrm.entity.vo.common_vo import CommonDataModel


class ClashModel(CommonDataModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    clash_id: int | str | None = None
    name: Optional[str] = None
    api_url: Optional[str] = None
    secret: Optional[str] = None
    status: Optional[int] = None  # online / offline
    bind_subscriptions: Optional[str] = None


class ClashCreatModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    name: Optional[str] = None
    api_url: Optional[str] = None
    secret: Optional[str] = None
    status: Optional[int] = None  # online / offline
    bind_subscriptions: Optional[str] = None


class ClashUpdateModel(CommonDataModel, ClashCreatModel):
    clash_id: int | str | None = None