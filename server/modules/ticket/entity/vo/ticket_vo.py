from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from module_admin.annotation.pydantic_annotation import as_query
from module_hrm.entity.vo.common_vo import QueryModel
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus


class TicketBaseModel(BaseModel):
    """
    工单基础模型，用于新增、编辑和详情返回。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    ticket_id: int | None = None
    ticket_no: str | None = None
    title: str | None = Field(default=None, description="工单标题")
    description: str | None = Field(default=None, description="工单描述")
    project_id: int | None = Field(default=None, description="所属项目ID")
    project_name: str | None = Field(default=None, description="所属项目名称")
    merchant_name: str | None = Field(default=None, description="所属项目名称（兼容历史字段 merchantName）")
    module_id: int | None = Field(default=None, description="所属模块ID")
    module_name: str | None = Field(default=None, description="所属模块名称")
    version_key: str | None = Field(default=None, description="版本号")
    need_log_pull: bool | None = Field(default=None, description="创建工单后是否自动拉取日志")
    log_pull_config: dict[str, Any] | None = Field(default=None, description="创建工单时的日志拉取配置")
    category_id: int | None = Field(default=None, description="问题分类ID")
    category_name: str | None = Field(default=None, description="问题分类名称")
    status: str | None = Field(default=TicketStatus.PENDING.value, description="当前状态")
    customer_priority: str | None = Field(default="P3", description="对方优先级")
    internal_priority: str | None = Field(default="P3", description="内部优先级")
    severity: str | None = Field(default=None, description="严重等级")
    source: str | None = Field(default=None, description="工单来源")
    reporter_id: int | None = Field(default=None, description="提单人ID")
    reporter_name: str | None = Field(default=None, description="提单人名称")
    current_assignee_id: int | None = Field(default=None, description="当前处理人ID")
    current_assignee_name: str | None = Field(default=None, description="当前处理人名称")
    is_problem: bool | None = Field(default=None, description="是否真实问题")
    root_cause: str | None = Field(default=None, description="最终根因")
    solution: str | None = Field(default=None, description="最终解决方案")
    started_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    first_response_at: datetime | None = None
    total_process_seconds: int | None = None
    tags: dict[str, Any] | list[str] | None = Field(default=None, description="标签")
    extra_data: dict[str, Any] | None = Field(default=None, description="扩展上下文")
    ai_analysis: dict[str, Any] | None = Field(default=None, description="AI分析预留结果")
    create_by: str | None = None
    update_by: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class TicketCreateModel(TicketBaseModel):
    """
    新增工单模型。
    """

    ticket_no: str = Field(description="工单编号")
    title: str = Field(description="工单标题")


class TicketUpdateModel(TicketBaseModel):
    """
    编辑工单模型。
    """

    ticket_id: int = Field(description="工单ID")


@as_query
class TicketQueryModel(QueryModel):
    """
    工单列表查询模型。
    """

    ticket_no: str | None = Field(default=None, description="工单编号")
    title: str | None = Field(default=None, description="工单标题")
    status: str | None = Field(default=None, description="当前状态")
    project_id: int | None = Field(default=None, description="所属项目ID")
    module_id: int | None = Field(default=None, description="所属模块ID")
    category_id: int | None = Field(default=None, description="问题分类ID")
    customer_priority: str | None = Field(default=None, description="对方优先级")
    internal_priority: str | None = Field(default=None, description="内部优先级")
    source: str | None = Field(default=None, description="工单来源")
    current_assignee_id: int | None = Field(default=None, description="当前处理人ID")
    reporter_id: int | None = Field(default=None, description="提单人ID")
    keyword: str | None = Field(default=None, description="关键字，匹配标题、描述、根因、解决方案")


class TicketAssignModel(BaseModel):
    """
    工单指派模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    to_user_id: int | None = Field(default=None, description="目标处理人ID")
    to_user_name: str | None = Field(default=None, description="目标处理人名称")
    reason: str | None = Field(default=None, description="指派原因")


class TicketStatusChangeModel(BaseModel):
    """
    工单状态流转模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    to_status: str = Field(description="目标状态")
    comment: str | None = Field(default=None, description="流转说明")
    root_cause: str | None = Field(default=None, description="最终根因")
    solution: str | None = Field(default=None, description="最终解决方案")
    is_problem: bool | None = Field(default=None, description="是否真实问题")


class TicketCommentCreateModel(BaseModel):
    """
    新增工单评论模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    content: str = Field(description="评论内容")
    is_internal: bool = Field(default=False, description="是否内部评论")


class TicketEventCreateModel(BaseModel):
    """
    新增工单事件模型，用于排查过程、复现步骤、日志分析、修复上线等结构化记录。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_type: str = Field(default=TicketEventType.ANALYSIS.value, description="事件类型")
    content: str | None = Field(default=None, description="事件说明")
    event_data: dict[str, Any] | None = Field(default=None, description="结构化事件数据")


class TicketRcaModel(BaseModel):
    """
    工单 RCA 模型，用于结构化保存现象、影响范围、排查过程、根因、修复和预防方案。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: int | None = None
    ticket_id: int | None = None
    symptom: str | None = None
    root_cause_category: str | None = None
    root_cause_detail: str | None = None
    trigger_reason: str | None = None
    impact_scope: str | None = None
    reproduce_steps: str | None = None
    investigation_process: str | None = None
    fix_solution: str | None = None
    verify_method: str | None = None
    prevention_solution: str | None = None
    structured_data: dict[str, Any] | None = None
    created_by_id: int | None = None
    created_by_name: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class TicketAiRepoMappingBaseModel(BaseModel):
    """
    工单 AI 仓库映射基础模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    mapping_id: int | None = None
    project_id: int = Field(description="所属项目ID")
    project_name: str = Field(default="", description="项目名称")
    version_key: str = Field(description="版本标识")
    repo_url: str = Field(default="", description="仓库地址")
    branch_name: str = Field(default="", description="分支名称")
    local_repo_path: str = Field(default="", description="本地仓库路径")
    workspace_root: str = Field(default="", description="工作区根目录")
    worker_command: str = Field(default="", description="Worker执行命令")
    is_default: bool = Field(default=False, description="是否默认映射")
    enabled: bool = Field(default=True, description="是否启用")
    remark: str | None = Field(default=None, description="备注")
    extra_data: dict[str, Any] | None = Field(default=None, description="扩展字段")
    create_by: str | None = None
    update_by: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


@as_query
class TicketAiRepoMappingQueryModel(QueryModel):
    """
    工单 AI 仓库映射查询模型。
    """

    project_id: int | None = Field(default=None, description="所属项目ID")
    version_key: str | None = Field(default=None, description="版本标识")
    enabled: bool | None = Field(default=None, description="是否启用")
    keyword: str | None = Field(default=None, description="项目名、版本或仓库关键字")


class TicketAiRepoMappingCreateModel(TicketAiRepoMappingBaseModel):
    """
    工单 AI 仓库映射新增模型。
    """

    project_id: int = Field(description="所属项目ID")
    version_key: str = Field(description="版本标识")


class TicketAiRepoMappingUpdateModel(TicketAiRepoMappingBaseModel):
    """
    工单 AI 仓库映射编辑模型。
    """

    mapping_id: int = Field(description="映射ID")


class TicketAiAnalysisRequestModel(BaseModel):
    """
    工单 AI 分析提交模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    mapping_id: int | None = Field(default=None, description="仓库映射ID，兼容手动指定")
    version_key: str = Field(description="版本标识，用于匹配仓库映射")
    log_pull_record_id: int | None = Field(default=None, description="指定日志拉取记录ID")
    agent_code: str | None = Field(default=None, description="执行AI分析的Agent编码")
    force_refresh: bool = Field(default=False, description="是否强制重新分析")

    @model_validator(mode="after")
    def validate_request(self):
        """
        校验 AI 分析提交参数。
        :return: 当前模型
        """
        self.version_key = str(self.version_key or "").strip()
        if not self.version_key:
            raise ValueError("版本号不能为空")
        self.agent_code = str(self.agent_code or "").strip() or None
        return self


class TicketAiAnalysisTaskModel(BaseModel):
    """
    工单 AI 分析任务模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    task_id: int | None = None
    ticket_id: int | None = None
    project_id: int | None = None
    mapping_id: int | None = None
    project_name: str | None = None
    version_key: str | None = None
    repo_url: str | None = None
    branch_name: str | None = None
    local_repo_path: str | None = None
    workspace_root: str | None = None
    workspace_path: str | None = None
    prompt_path: str | None = None
    result_path: str | None = None
    command_line: str | None = None
    status: str | None = None
    status_desc: str | None = None
    error_message: str | None = None
    prompt_text: str | None = None
    raw_output: str | None = None
    analysis_result: dict[str, Any] | None = None
    analysis_context: dict[str, Any] | None = None
    source_log_pull_record_id: int | None = None
    source_log_view_mode: str | None = None
    submitted_by_id: int | None = None
    submitted_by_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


@as_query
class TicketAiAnalysisTaskQueryModel(QueryModel):
    """
    工单 AI 分析任务查询模型。
    """

    status: str | None = Field(default=None, description="任务状态")
    ticket_id: int | None = Field(default=None, description="工单ID")
    version_key: str | None = Field(default=None, description="版本标识")


class KnowledgeArticleModel(BaseModel):
    """
    知识库文章模型，用于沉淀历史解决方案和复盘内容。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    article_id: int | None = None
    title: str | None = Field(default=None, description="文章标题")
    content: str | None = Field(default=None, description="文章内容")
    category: str | None = Field(default=None, description="文章分类")
    tags: dict[str, Any] | list[str] | None = Field(default=None, description="标签")
    related_ticket_ids: dict[str, Any] | list[int] | None = Field(default=None, description="关联工单ID")
    embedding_status: str | None = Field(default="pending", description="向量生成状态")
    created_by_id: int | None = None
    created_by_name: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


@as_query
class KnowledgeArticleQueryModel(QueryModel):
    """
    知识库文章查询模型。
    """

    title: str | None = Field(default=None, description="文章标题")
    category: str | None = Field(default=None, description="文章分类")
    keyword: str | None = Field(default=None, description="关键字，匹配标题和内容")


class WorkflowStatusModel(BaseModel):
    """
    工作流状态模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: int | None = None
    code: str = Field(description="状态编码")
    name: str = Field(description="状态名称")
    is_start: bool = Field(default=False, description="是否开始状态")
    is_end: bool = Field(default=False, description="是否结束状态")
    order_num: int = Field(default=0, description="排序")


class WorkflowTransitionModel(BaseModel):
    """
    工作流流转模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    id: int | None = None
    from_status: str = Field(description="原状态")
    to_status: str = Field(description="目标状态")
    allowed_roles: dict[str, Any] | list[str] | None = Field(default=None, description="允许角色")
    target_assignee_id: int | None = Field(default=None, description="流转后默认处理人ID")
    target_assignee_name: str | None = Field(default=None, description="流转后默认处理人名称")
    notify_enabled: bool = Field(default=False, description="流转完成后是否保留通知入口")
    notify_remark: str | None = Field(default=None, description="通知备注或后续渠道预留说明")
    need_comment: bool = Field(default=False, description="是否需要说明")
    need_resolution: bool = Field(default=False, description="是否需要解决方案")


@as_query
class TicketUserOptionQueryModel(BaseModel):
    """
    工单用户选择器查询模型。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    keyword: str | None = Field(default=None, description="用户名、昵称或手机号关键字")
    limit: int = Field(default=20, description="返回数量限制")


@as_query
class TicketStatisticsQueryModel(QueryModel):
    """
    工单统计查询模型。
    """

    begin_time: date | datetime | str | None = Field(default=None, description="开始时间")
    end_time: date | datetime | str | None = Field(default=None, description="结束时间")
