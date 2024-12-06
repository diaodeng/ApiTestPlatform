import json
from typing import Optional, Dict, Any

from pydantic import model_validator, field_serializer, ConfigDict, Field
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel, QueryModel
from utils.common_util import CamelCaseUtil


class ForwardRulesModel(CommonDataModel):
    """

    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    rule_id: Optional[int] = None
    rule_name: Optional[str] = None
    origin_url: list | str | None = None
    target_url: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[int] = None

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values = CamelCaseUtil.transform_result(values)
        origin_url_data = values.get('originUrl')
        if not origin_url_data:
            values["originUrl"] = []
        elif not isinstance(origin_url_data, list):
            values["originUrl"] = json.loads(origin_url_data)

        return values

    @field_serializer('origin_url')
    def origin_url_handel(self, origin_url_data: Any):
        if isinstance(origin_url_data, str):
            return origin_url_data
        else:
            return json.dumps(origin_url_data, ensure_ascii=False)


@as_query
@as_form
class ForwardRulesQueryModel(QueryModel, ForwardRulesModel):
    pass


class ForwardRulesDeleteModel(ForwardRulesModel):
    rule_id: list = Field(default_factory=lambda: [])


class ForwardRulesDetailModel(CommonDataModel):
    """

    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    rule_id: Optional[int] = None
    rule_detail_id: Optional[int] = None
    match_type: Optional[int] = None  # module_hrm.enums.enums.ForwardRuleMatchTypeEnum
    rule_detail_name: Optional[str] = None
    origin_url: str | None = None
    target_url: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[int] = None


@as_query
@as_form
class ForwardRulesDetailQueryModel(QueryModel, ForwardRulesDetailModel):
    pass


class ForwardRulesDetailDeleteModel(ForwardRulesDetailModel):
    rule_id: list = Field(default_factory=lambda: [])
    rule_detail_id: list = Field(default_factory=lambda: [])