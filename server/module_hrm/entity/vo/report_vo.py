from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from module_hrm.enums.enums import CaseRunStatus


class ReportListModel(CommonDataModel):
    """
    报告查询模型
    """
    report_id: Optional[int] = None
    report_name: str = ""
    start_at: Any = ""
    test_duration: float = 0
    status: int = CaseRunStatus.passed.value
    total: int = 0
    success: int = 0


@as_query
class  ReportQueryModel(QueryModel, ReportListModel):
    """
    报告查询模型
    """
    report_name: str | None = None


class ReportCreatModel(ReportListModel):
    """
    报告查询模型
    """
    report_id: int | None = None
    report_content: str | None = None


class ReportDelModel(BaseModel):
    """
    报告删除与清理模型。
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    report_ids: list | None = Field(default_factory=lambda: [])
    begin_time: date | datetime | str | None = Field(default=None, description="开始时间")
    end_time: date | datetime | str | None = Field(default=None, description="结束时间")
    user_id: int | None = Field(default=None, description="用户ID，选填")

    @model_validator(mode="after")
    def validate_cleanup_scope(self):
        """
        校验清理范围至少包含报告ID或时间范围。

        :return: 当前模型。
        """
        normalized_ids: list[int] = []
        for item in self.report_ids or []:
            if item in (None, ""):
                continue
            try:
                normalized_ids.append(int(item))
            except Exception as exc:
                raise ValueError(f"reportIds 含有非法值: {item}") from exc
        self.report_ids = normalized_ids
        self.user_id = int(self.user_id) if self.user_id not in (None, "") else None
        has_ids = bool(self.report_ids)
        has_range = self.begin_time not in (None, "") or self.end_time not in (None, "")
        if has_range and (self.begin_time in (None, "") or self.end_time in (None, "")):
            raise ValueError("时间范围请同时填写开始时间和结束时间")
        if not has_ids and not has_range:
            raise ValueError("reportIds 或时间范围至少提供一项")
        return self
