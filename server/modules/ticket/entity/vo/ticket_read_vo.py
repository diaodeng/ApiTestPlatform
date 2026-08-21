from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query


class _TicketLimitQueryModel(BaseModel):
    """工单按需读取接口的数量参数基类。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    limit: int = Field(description="返回最近或最相似的数量")

    @model_validator(mode="after")
    def normalize_limit(self):
        """将数量限制在安全范围内，避免一次读取过多记录。"""
        try:
            self.limit = int(self.limit)
        except (TypeError, ValueError):
            self.limit = 5
        self.limit = min(max(self.limit, 1), 100)
        return self


@as_query
class TicketSimilarQueryModel(_TicketLimitQueryModel):
    """相似工单查询参数，默认返回 5 条。"""

    limit: int = Field(default=5, description="返回相似工单数量，默认5，最大100")


@as_query
class TicketMessagesPageQueryModel(_TicketLimitQueryModel):
    """协同消息按需查询参数，默认返回最近 20 条。"""

    limit: int = Field(default=20, description="返回最近消息数量，默认20，最大100")


@as_query
class TicketSnapshotsPageQueryModel(_TicketLimitQueryModel):
    """ACR 快照按需查询参数，默认返回最近 10 条。"""

    limit: int = Field(default=10, description="返回最近快照数量，默认10，最大100")


class TicketSimilarItemModel(BaseModel):
    """相似工单摘要白名单模型，禁止透出完整工单描述和扩展数据。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ticket_id: str
    ticket_no: str | None = None
    ticket_url: str | None = None
    title: str | None = None
    status: str | None = None
    project_name: str | None = None
    module_name: str | None = None
    issue_type_id: str | None = None
    issue_type_name: str | None = None
    problem_pattern_code: str | None = None
    problem_pattern_name: str | None = None
    customer_priority: str | None = None
    internal_priority: str | None = None
    severity: str | None = None
    root_cause_type: str | None = None
    solution_type: str | None = None
    resolution_code: str | None = None
    resolution_name: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    score: float = 0.0


class TicketSimilarResponseModel(BaseModel):
    """相似工单查询响应 data 模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: str
    message: str = ""
    items: list[TicketSimilarItemModel] = Field(default_factory=list)


class TicketMessagePageItemModel(BaseModel):
    """按需消息返回模型，主键统一序列化为字符串。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str | None = None
    ticket_id: str | None = None
    role: str | None = None
    message_type: str | None = None
    content: str | None = None
    attachments: dict[str, Any] | list[dict[str, Any]] | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    created_by_id: str | None = None
    created_by_name: str | None = None
    create_time: Any | None = None

    @field_validator("id", "ticket_id", "reference_id", "created_by_id", mode="before")
    @classmethod
    def serialize_message_ids(cls, value: Any) -> str | None:
        """将消息主键转换为字符串，避免前端整数精度丢失。"""
        return str(value) if value is not None else None


class TicketSnapshotPageItemModel(BaseModel):
    """按需快照返回模型，主键统一序列化为字符串。"""

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: str | None = None
    ticket_id: str | None = None
    version: int | None = None
    summary: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    prevention: str | None = None
    risk: str | None = None
    owner: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    structured_data: dict[str, Any] | None = None
    created_by_id: str | None = None
    create_time: Any | None = None

    @field_validator("id", "ticket_id", "source_id", "created_by_id", mode="before")
    @classmethod
    def serialize_snapshot_ids(cls, value: Any) -> str | None:
        """将快照主键转换为字符串，避免前端整数精度丢失。"""
        return str(value) if value is not None else None


class TicketMessagesPageResponseModel(BaseModel):
    """协同消息按需查询响应 data 模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[TicketMessagePageItemModel] = Field(default_factory=list)
    limit: int
    has_more: bool = False


class TicketSnapshotsPageResponseModel(BaseModel):
    """ACR 快照按需查询响应 data 模型。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    items: list[TicketSnapshotPageItemModel] = Field(default_factory=list)
    limit: int
    has_more: bool = False


class TicketSummaryModel(BaseModel):
    """工单轻量概览响应模型，只保留基础、版本、Issue、关系码和必要摘要。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ticket_id: str
    ticket_no: str | None = None
    ticket_url: str | None = None
    title: str | None = None
    description: str | None = None
    original_description: str | None = None
    ai_translation: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    project_code: str | None = None
    merchant_name: str | None = None
    module_id: str | None = None
    module_name: str | None = None
    module_code: str | None = None
    status: str | None = None
    issue_type_id: str | None = None
    issue_type_name: str | None = None
    issue_id: str | None = None
    issue_no: str | None = None
    issue_title: str | None = None
    issue_relation_type: str | None = None
    issue_confirmed: bool | None = None
    issue: dict[str, Any] | None = None
    affected_version_id: str | None = None
    affected_version: str | None = None
    planned_fix_version_id: str | None = None
    planned_fix_version: str | None = None
    fixed_version_id: str | None = None
    fixed_version: str | None = None
    released_version_id: str | None = None
    released_version: str | None = None
    version_key: str | None = None
    customer_priority: str | None = None
    internal_priority: str | None = None
    severity: str | None = None
    root_cause_type: str | None = None
    solution_type: str | None = None
    resolution_code: str | None = None
    resolution_name: str | None = None
    problem_pattern_code: str | None = None
    problem_pattern_name: str | None = None
    is_problem: bool | None = None
    root_cause: str | None = None
    solution: str | None = None
    source: str | None = None
    reporter_id: str | None = None
    reporter_name: str | None = None
    current_assignee_id: str | None = None
    current_assignee_name: str | None = None
    first_line_assignee_id: str | None = None
    first_line_assignee_name: str | None = None
    internal_owner_id: str | None = None
    internal_owner_name: str | None = None
    submit_time: Any | None = None
    started_at: Any | None = None
    resolved_at: Any | None = None
    closed_at: Any | None = None
    processed_at: Any | None = None
    released_at: Any | None = None
    verified_at: Any | None = None
    processing_conclusion_status: str | None = None
    latest_log_pull: dict[str, Any] | None = None
    latest_ai_analysis: dict[str, Any] | None = None
