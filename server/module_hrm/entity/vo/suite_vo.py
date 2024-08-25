import json

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator
from pydantic.alias_generators import to_camel
from typing import Union, Optional, List, Dict, Text, Any
from datetime import datetime
from module_admin.annotation.pydantic_annotation import as_query
from utils.common_util import CamelCaseUtil


class SuiteModel(BaseModel):
    """
    测试套件表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    suite_id: Optional[int] = None
    suite_name: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[str] = None
    del_flag: Optional[str] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


@as_query
class SuiteQueryModel(SuiteModel):
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


class SuiteDetailModel(BaseModel):
    """
    测试套件详情表对应pydantic模型
    """
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    suite_detail_id: Optional[int] = None
    suite_id: Optional[int] = None
    suite_name: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[str] = None
    del_flag: Optional[str] = None
    create_by: Optional[str] = None
    create_time: Optional[datetime] = None
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


@as_query
class SuiteDetailQueryModel(SuiteModel):
    """
    测试套件详情不分页查询模型
    """
    begin_time: Optional[str] = None
    end_time: Optional[str] = None


class DeleteDetailSuiteModel(BaseModel):
    """
    删除测试套件详情模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    suite_detail_ids: str
    update_by: Optional[str] = None
    update_time: Optional[str] = None
