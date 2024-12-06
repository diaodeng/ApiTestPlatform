from typing import Any

from pydantic import field_serializer

from module_hrm.entity.vo.forward_rules_vo import ForwardRulesModel


class ForwardRulesModelForApi(ForwardRulesModel):
    """
    只要不是最后入库数据都用这个模型

    """

    @field_serializer('origin_url')
    def origin_url_handel(self, origin_url_data: Any):
        return origin_url_data
