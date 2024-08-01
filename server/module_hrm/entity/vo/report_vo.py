import json

from pydantic import BaseModel, ConfigDict, Field, field_serializer, root_validator, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Any, Text, Dict

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel, CommonDataModel


@as_query
class ReportQueryModel(QueryModel):
    """
    报告查询模型
    """
    report_name: Text | None = None


class ReportListModel(CommonDataModel):
    """
    报告查询模型
    """
    report_id: int
    report_name: Text = ""
    start_at: Any = ""
    status: int = 1
    total: int = 0
    success: int = 0


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
    report_ids: list | None = []
