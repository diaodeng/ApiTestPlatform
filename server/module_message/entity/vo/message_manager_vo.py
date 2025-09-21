from typing import Optional, Any

from pydantic import Field

from module_admin.annotation.pydantic_annotation import as_query, as_form
from ..dto.message_manager_dto import MessageManagerModel, MessageConfigModel


@as_query
@as_form
class MessageManagerPageQueryModel(MessageManagerModel):
    """
    分页查询模型
    """
    page_num: int = 1
    page_size: int = 10

    only_self: Optional[bool] = False


class MessageManagerModelForApi(MessageManagerModel):
    """
    MessageManagerModel和模块关联表对应pydantic模型
    """
    config: MessageConfigModel | None = Field(default_factory=lambda: {})

    def config_data(self, request: Any):
        return request


class MessageDeleteModel(MessageManagerModel):
    """
    MessageManagerModel和模块关联表对应pydantic模型
    """
    message_ids: list[int] = Field(default_factory=lambda: [])