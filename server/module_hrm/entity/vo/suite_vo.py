import json

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Dict, Text, Any
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from utils.common_util import CamelCaseUtil


class SuiteModel(CommonDataModel):
    """
    测试套件表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    suite_id: Optional[int] = None
    suite_name: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[str] = None


@as_query
class SuiteQueryModel(SuiteModel, QueryModel):
    """
    测试套件管理不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class DeleteSuiteModel(BaseModel):
    """
    删除测试套件模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    suite_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None


@as_query
@as_form
class SuitePageQueryModel(SuiteQueryModel):
    """
    测试套件分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: bool = False


class SuiteDetailModel(CommonDataModel):
    """
    测试套件详情表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    suite_detail_id: Optional[int] = None
    suite_id: Optional[int] = None
    data_id: Optional[int] = None
    data_type: Optional[int] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[str] = None


@as_query
class SuiteDetailQueryModel(SuiteDetailModel, QueryModel):
    """
    测试套件详情不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


@as_query
@as_form
class SuiteDetailPageQueryModel(SuiteDetailQueryModel):
    """
    测试套件详情分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: bool = False


class DeleteDetailSuiteModel(BaseModel):
    """
    删除测试套件详情模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    suite_detail_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
