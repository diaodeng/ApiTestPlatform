from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_form, as_query
from module_hrm.entity.dto.mock_dto import MockModel, MockRequestModel, MockResponseModel
from module_hrm.entity.vo.common_vo import QueryModel


@as_query
@as_form
class MockRequestPageQueryModel(QueryModel, MockRequestModel):
    """
    查询模型
    """
    pass


class AddMockRequestModel(MockRequestModel):
    """
    新增mock规则模型
    """
    pass


class DeleteMockRequestModel(BaseModel):
    """
    删除mock规则模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    rule_request_ids: list[str|int] = Field(default_factory=lambda : [])
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


@as_query
@as_form
class MockResponsePageQueryModel(QueryModel, MockResponseModel):
    """
    查询模型
    """
    response_condition: Optional[str] = None
    headers_template: Optional[str] = None


class AddMockResponseModel(MockResponseModel):
    """
    新增mock规则模型
    """
    pass


class DeleteMockResponseModel(BaseModel):
    """
    删除mock规则模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    rule_response_ids: list[str|int] = Field(default_factory=lambda : [])
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None


@as_query
@as_form
class MockPageQueryModel(QueryModel, MockModel):
    """
    查询模型
    """
    rule_condition: Optional[str] = None
    pass


class AddMockRuleModel(MockModel):
    """
    新增mock规则模型
    """
    request: Optional[AddMockRequestModel] = None
    response: Optional[AddMockResponseModel] = None


class DeleteMockRuleModel(BaseModel):
    """
    删除mock规则模型
    """
    model_config = ConfigDict(alias_generator=to_camel)

    rule_ids: list[int|str] = Field(default_factory=lambda : [])
    update_by: Optional[str] = None
    update_time: Optional[datetime] = None