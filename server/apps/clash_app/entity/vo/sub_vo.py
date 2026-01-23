from typing import Optional

from pydantic import ConfigDict, BaseModel
from pydantic.alias_generators import to_camel

from module_hrm.entity.vo.common_vo import CommonDataModel


class SubsModel(CommonDataModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    sub_id: int | str | None = None
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None  # clash / sing-box / raw
    enabled: Optional[int] = None
    update_interval: Optional[int] = None


class SubsCreatModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None  # clash / sing-box / raw
    enabled: Optional[int] = None
    update_interval: Optional[int] = None


class SubsUpdateModel(CommonDataModel, SubsCreatModel):
    sub_id: int | str | None = None
