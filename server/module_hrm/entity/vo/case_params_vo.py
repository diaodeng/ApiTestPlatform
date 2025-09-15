from typing import Optional

from pydantic import ConfigDict, BaseModel
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import QueryModel


@as_query
@as_form
class CaseParamsQueryModel(QueryModel):
    case_id: Optional[int | str] = None
    enabled: Optional[bool] = None
    row_id: Optional[str] = None


class CaseParamsDeleteModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    case_id: Optional[int | str] = None
    row_ids: Optional[list[str|int]] = None
