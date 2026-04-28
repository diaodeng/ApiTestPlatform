from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel


class RunErrorEventModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    error_type: str = 'exception'
    error_source: str = ''
    error_subtype: str = ''
    error_name: str = ''
    error_template: str = ''
    fingerprint: str = ''
    step_id: str = ''
    step_name: str = ''
    check_key: str = ''
    assert_name: str = ''
    expected_value: str = ''
    actual_value: str = ''
    error_message: str = ''
    error_stack: str = ''


class RunErrorRecordModel(CommonDataModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    error_id: Optional[int] = None
    detail_id: Optional[int] = None
    report_id: Optional[int] = None
    run_id: Optional[int] = None
    run_name: Optional[str] = None
    error_type: str = ''
    error_source: str = ''
    error_subtype: str = ''
    error_name: str = ''
    error_template: str = ''
    fingerprint: str = ''
    step_id: str = ''
    step_name: str = ''
    check_key: str = ''
    assert_name: str = ''
    expected_value: str = ''
    actual_value: str = ''
    error_message: str = ''
    error_stack: str = ''


class RunErrorTypeStatModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    error_type: str = ''
    count: int = 0


class RunAssertReasonStatModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    fingerprint: str = ''
    error_template: str = ''
    error_subtype: str = ''
    assert_name: str = ''
    check_key: str = ''
    count: int = 0
    case_count: int = 0


class RunErrorSummaryModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    report_id: int
    total_count: int = 0
    assert_fail_count: int = 0
    exception_count: int = 0
    error_type_stats: list[RunErrorTypeStatModel] = Field(default_factory=list)
    assert_reason_stats: list[RunAssertReasonStatModel] = Field(default_factory=list)


@as_query
class RunErrorQueryModel(QueryModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    report_id: Optional[int] = None
    detail_id: Optional[int] = None
    run_id: Optional[int] = None
    error_type: Optional[str] = None
    fingerprint: Optional[str] = None
