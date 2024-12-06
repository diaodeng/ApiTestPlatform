from typing import Any

from pydantic import Field

from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase


class CaseModelForApi(CaseModel):
    """
    用例信息表对应pydantic模型, 用于编辑用例页面,只要不是最后入库数据都用这个模型

    """
    request: TestCase = Field(default_factory=lambda: {})

    def request_data(self, request: Any):
        return request

    def include_data(self, include: Any):
        return include
