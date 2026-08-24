from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel


class TicketIssueBaseModel(BaseModel):
    """
    问题实例基础模型，用于创建、编辑和详情返回。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    issue_id: int | None = None
    issue_no: str | None = Field(default=None, description="问题实例编号")
    title: str | None = Field(default=None, description="问题标题")
    summary: str | None = Field(default=None, description="问题摘要")
    status: str | None = Field(default=None, description="问题状态：open/processing/resolved/closed")
    severity: str | None = Field(default=None, description="严重等级")
    project_id: int | None = Field(default=None, description="所属项目ID")
    project_name: str | None = Field(default=None, description="所属项目名称")
    module_id: int | None = Field(default=None, description="所属模块ID")
    module_name: str | None = Field(default=None, description="所属模块名称")
    root_cause_type: str | None = Field(default=None, description="根因分类")
    problem_pattern_code: str | None = Field(default=None, description="细分问题类型编码")
    problem_pattern_name: str | None = Field(default=None, description="细分问题类型名称")
    owner_id: int | None = Field(default=None, description="负责人ID")
    owner_name: str | None = Field(default=None, description="负责人名称")
    first_ticket_id: int | None = Field(default=None, description="首张工单ID")
    first_ticket_no: str | None = Field(default=None, description="首张工单号")
    affected_ticket_count: int | None = Field(default=None, description="影响工单数")
    create_by: str | None = None
    update_by: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None

    @field_validator(
        "issue_id",
        "project_id",
        "module_id",
        "owner_id",
        "first_ticket_id",
        "affected_ticket_count",
        mode="before",
    )
    @classmethod
    def normalize_optional_integer(cls, value):
        """
        将表单传入的空字符串归一化为空值，避免可选整数校验失败。
        :param value: 原始字段值
        :return: 可供 Pydantic 继续校验的值
        """
        return None if value is None or (isinstance(value, str) and not value.strip()) else value


class TicketIssueCreateModel(TicketIssueBaseModel):
    """
    创建问题实例模型。
    """

    title: str = Field(description="问题标题")

    @model_validator(mode="after")
    def validate_create(self):
        """
        清理创建入参，避免写入空白标题和非法状态。
        :return: 当前模型
        """
        self.title = str(self.title or "").strip()
        if not self.title:
            raise ValueError("问题标题不能为空")
        self.status = normalize_issue_status(self.status)
        return self


class TicketIssueUpdateModel(TicketIssueBaseModel):
    """
    编辑问题实例模型。
    """

    issue_id: int = Field(description="问题实例ID")

    @model_validator(mode="after")
    def validate_update(self):
        """
        清理编辑入参，避免写入非法状态。
        :return: 当前模型
        """
        if self.title is not None:
            self.title = str(self.title or "").strip()
            if not self.title:
                raise ValueError("问题标题不能为空")
        if self.status is not None:
            self.status = normalize_issue_status(self.status)
        return self


@as_query
class TicketIssueTicketOptionQueryModel(BaseModel):
    """
    问题实例绑定工单选择器查询模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    keyword: str | None = Field(default=None, description="工单号或标题关键字")
    project_id: int | None = Field(default=None, description="项目ID")
    module_id: int | None = Field(default=None, description="模块ID")
    limit: int = Field(default=20, description="返回数量限制")

    @model_validator(mode="after")
    def normalize_query(self):
        """
        归一化工单选择器查询参数。
        :return: 当前模型
        """
        self.keyword = str(self.keyword or "").strip() or None
        self.limit = min(max(int(self.limit or 20), 1), 20)
        return self


class TicketIssueBindByTicketNoModel(BaseModel):
    """
    按业务工单号绑定问题实例模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ticket_no: str = Field(description="业务工单号")
    relation_type: str | None = Field(default="manual", description="归属类型")
    confirmed: bool = Field(default=True, description="是否人工确认")
    remark: str | None = Field(default=None, description="操作备注")

    @model_validator(mode="after")
    def normalize_bind_by_no(self):
        """
        清理按工单号绑定参数。
        :return: 当前模型
        """
        self.ticket_no = str(self.ticket_no or "").strip()
        if not self.ticket_no:
            raise ValueError("ticketNo 不能为空")
        self.relation_type = normalize_relation_type(self.relation_type)
        self.remark = str(self.remark or "").strip() or None
        return self


class TicketIssueBatchBindModel(BaseModel):
    """
    批量绑定工单到已有问题实例模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ticket_nos: list[str] = Field(default_factory=list, description="业务工单号列表")
    issue_id: int = Field(description="目标问题实例ID")
    relation_type: str | None = Field(default="manual", description="归属类型")
    confirmed: bool = Field(default=True, description="是否人工确认")
    allow_reassign: bool = Field(default=False, description="是否允许覆盖已有问题归属")
    remark: str | None = Field(default=None, description="批量归因说明")

    @model_validator(mode="after")
    def normalize_batch_bind(self):
        """
        清理批量绑定参数并限制单次处理规模。
        :return: 当前模型
        """
        normalized_nos: list[str] = []
        for ticket_no in self.ticket_nos or []:
            value = str(ticket_no or "").strip()
            if value and value not in normalized_nos:
                normalized_nos.append(value)
        if not normalized_nos:
            raise ValueError("ticketNos 至少需要提供一个工单号")
        if len(normalized_nos) > 200:
            raise ValueError("单次最多关联 200 张工单")
        self.ticket_nos = normalized_nos
        self.relation_type = normalize_relation_type(self.relation_type)
        self.remark = str(self.remark or "").strip() or None
        return self


@as_query
class TicketIssueQueryModel(QueryModel):
    """
    问题实例分页查询模型。
    """

    issue_no: str | None = Field(default=None, description="问题实例编号")
    title: str | None = Field(default=None, description="问题标题")
    status: str | None = Field(default=None, description="问题状态")
    project_id: int | None = Field(default=None, description="所属项目ID")
    module_id: int | None = Field(default=None, description="所属模块ID")
    owner_id: int | None = Field(default=None, description="负责人ID")
    problem_pattern_code: str | None = Field(default=None, description="细分问题类型编码")
    keyword: str | None = Field(default=None, description="关键字，匹配编号、标题、摘要")


class TicketIssueBindModel(BaseModel):
    """
    工单绑定问题实例模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    issue_id: int = Field(description="问题实例ID")
    relation_type: str | None = Field(default="manual", description="归属类型")
    confirmed: bool = Field(default=True, description="是否人工确认")
    remark: str | None = Field(default=None, description="操作备注")

    @model_validator(mode="after")
    def normalize_bind(self):
        """
        归一化绑定参数。
        :return: 当前模型
        """
        self.relation_type = normalize_relation_type(self.relation_type)
        self.remark = str(self.remark or "").strip() or None
        return self


class TicketIssueCreateAndBindModel(TicketIssueCreateModel):
    """
    创建问题实例并绑定当前工单模型。
    """

    relation_type: str | None = Field(default="manual", description="归属类型")
    confirmed: bool = Field(default=True, description="是否人工确认")

    @model_validator(mode="after")
    def normalize_create_bind(self):
        """
        归一化创建并绑定参数。
        :return: 当前模型
        """
        self.status = normalize_issue_status(self.status)
        self.relation_type = normalize_relation_type(self.relation_type)
        return self


class TicketIssueSimilarBindModel(BaseModel):
    """
    从相似工单确认归因模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    similar_ticket_id: int = Field(description="相似工单ID")
    relation_type: str | None = Field(default="similar", description="归属类型")
    confidence: float | None = Field(default=None, description="相似度")
    remark: str | None = Field(default=None, description="备注")

    @model_validator(mode="after")
    def normalize_similar_bind(self):
        """
        归一化相似工单绑定参数。
        :return: 当前模型
        """
        self.relation_type = normalize_relation_type(self.relation_type)
        self.remark = str(self.remark or "").strip() or None
        if self.confidence is not None:
            self.confidence = min(max(float(self.confidence), 0), 1)
        return self


class TicketRelationCreateModel(BaseModel):
    """
    创建工单补充关系模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    source_ticket_id: int = Field(description="源工单ID")
    target_ticket_id: int = Field(description="目标工单ID")
    relation_type: str | None = Field(default="similar", description="关系类型")
    confidence: float | None = Field(default=None, description="置信度")
    source: str | None = Field(default="manual", description="来源")
    confirmed: bool = Field(default=False, description="是否确认")
    remark: str | None = Field(default=None, description="备注")

    @model_validator(mode="after")
    def normalize_relation(self):
        """
        归一化补充关系参数。
        :return: 当前模型
        """
        if self.source_ticket_id == self.target_ticket_id:
            raise ValueError("源工单和目标工单不能相同")
        self.relation_type = normalize_relation_type(self.relation_type)
        self.source = str(self.source or "manual").strip() or "manual"
        self.remark = str(self.remark or "").strip() or None
        if self.confidence is not None:
            self.confidence = min(max(float(self.confidence), 0), 1)
        return self


class TicketRelationModel(TicketRelationCreateModel):
    """
    工单补充关系返回模型。
    """

    relation_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


def normalize_issue_status(value: str | None) -> str:
    """
    归一化问题实例状态。
    :param value: 原始状态
    :return: 合法状态
    """
    status = str(value or "open").strip().lower()
    return status if status in {"open", "processing", "resolved", "closed"} else "open"


def normalize_relation_type(value: str | None) -> str:
    """
    归一化工单和问题实例的关系类型。
    :param value: 原始类型
    :return: 非空关系类型
    """
    return str(value or "manual").strip().lower() or "manual"


def dump_model(model: BaseModel, *, exclude_none: bool = True) -> dict[str, Any]:
    """
    将 Pydantic 模型转换为数据库字段字典。
    :param model: Pydantic 模型
    :param exclude_none: 是否排除空值
    :return: 字段字典
    """
    return model.model_dump(by_alias=False, exclude_none=exclude_none)
