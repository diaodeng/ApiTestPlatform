from typing import Any

from pydantic import Field

from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase
from module_hrm.entity.vo.common_vo import CommonDataModel


class CaseModelForApi(CaseModel):
    """
    用例信息表对应pydantic模型, 用于编辑用例页面,只要不是最后入库数据都用这个模型

    """
    request: TestCase = Field(default_factory=lambda: {})

    def request_data(self, request: Any):
        return request

    def include_data(self, include: Any):
        return include


class CaseParamsModel(CommonDataModel):
    case_id: int | str
    enabled: bool | None = None
    col_sort: int | None = None
    row_id: str
    sort_key: int | None = None
    col_name: str
    params_name: str
    col_value: str = ""
    params_type: int | None = None
