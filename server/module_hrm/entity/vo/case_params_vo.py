from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query
from module_hrm.entity.vo.common_vo import QueryModel


@as_query
@as_form
class CaseParamsQueryModel(QueryModel):
    case_id: Optional[int | str] = None
    enabled: Optional[bool | int] = None
    row_id: Optional[str] = None
    search_column: Optional[str] = None
    search_value: Optional[str] = None


class CaseParamsDeleteModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)
    case_id: Optional[int | str] = None
    row_ids: Optional[list[str | int]] = None


class CaseParamsCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    case_id: int | str
    row_data: dict[str, Any] = Field(default_factory=dict)


class CaseParamsColumnCreateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    case_id: int | str
    column_name: str
    default_value: Any = ""


class CaseParamsColumnDeleteModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    case_id: int | str
    column_name: str


class CaseParamsUpdateModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    case_id: int | str
    rows_data: list[dict[str, Any]] = Field(default_factory=list)
