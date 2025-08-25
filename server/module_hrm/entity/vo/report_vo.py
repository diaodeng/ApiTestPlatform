from typing import Optional, Any, Text

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel, CommonDataModel
from module_hrm.enums.enums import CaseRunStatus


class ReportListModel(CommonDataModel):
    """
    报告查询模型
    """
    report_id: Optional[int] = None
    report_name: Text = ""
    start_at: Any = ""
    test_duration: float = 0
    status: int = CaseRunStatus.passed.value
    total: int = 0
    success: int = 0


@as_query
class ReportQueryModel(QueryModel, ReportListModel):
    """
    报告查询模型
    """
    report_name: Text | None = None


class ReportCreatModel(ReportListModel):
    """
    报告查询模型
    """
    report_id: int | None = None
    report_content: Text | None = None


class ReportDelModel(BaseModel):
    """
    报告模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    report_ids: list | None = Field(default_factory=lambda: [])
