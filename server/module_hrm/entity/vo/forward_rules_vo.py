from typing import Optional

from module_admin.annotation.pydantic_annotation import as_query, as_form
from module_hrm.entity.vo.common_vo import CommonDataModel


@as_query
@as_form
class ForwardRulesModel(CommonDataModel):
    """

    """

    rule_id: Optional[int] = None
    rule_name: Optional[str] = None
    origin_url: Optional[str] = None
    target_url: Optional[str] = None
    order_num: Optional[int] = None
    simple_desc: Optional[str] = None
    status: Optional[int] = None
    del_flag: Optional[int] = None
