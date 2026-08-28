"""
工单导出请求/响应模型，定义导出范围、列配置的前端契约。
"""
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from modules.ticket.entity.vo.ticket_vo import TicketQueryModel


class TicketExportRequestModel(BaseModel):
    """
    工单导出请求模型。
    :param selected_ticket_ids: 前端表格选中的工单ID列表；有值时优先按选中导出
    :param columns: 导出列 key 列表；为空时默认导出全部列
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    selected_ticket_ids: list[int] = Field(default_factory=list, description="选中的工单ID列表")
    columns: list[str] = Field(default_factory=list, description="导出列 key 列表")
    query: TicketQueryModel | None = Field(default=None, description="未选择工单时使用的当前筛选条件")


class TicketIssueTicketExportRequestModel(BaseModel):
    """
    问题实例关联工单导出请求模型。
    :param selected_issue_ids: 选中的问题实例ID列表
    :param columns: 导出列 key 列表；为空时默认导出全部列
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    selected_issue_ids: list[int] = Field(default_factory=list, description="选中的问题实例ID列表")
    columns: list[str] = Field(default_factory=list, description="导出列 key 列表")
