from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from config.database import Base
from config.sqlalchemy_types import long_text_type
from modules.ticket.enums.ticket_enums import TicketStatus
from utils.snowflake import snowIdWorker


class Ticket(Base):
    """
    工单主表，保存工单当前态、最终归档态和后续 AI 分析预留字段。
    """

    __tablename__ = "ticket"

    ticket_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="工单ID"
    )
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="工单编号")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="工单标题")
    description: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="工单描述")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属项目ID")
    merchant_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="所属商家")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属模块ID")
    module_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="所属模块名称")
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="问题分类ID")
    category_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="问题分类名称")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TicketStatus.PENDING.value, comment="当前状态"
    )
    customer_priority: Mapped[str] = mapped_column(String(20), nullable=True, default="P3", comment="对方优先级")
    internal_priority: Mapped[str] = mapped_column(String(20), nullable=True, default="P3", comment="内部优先级")
    severity: Mapped[str] = mapped_column(String(50), nullable=True, default="", comment="严重等级")
    source: Mapped[str] = mapped_column(String(50), nullable=True, default="", comment="工单来源")
    reporter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="提单人ID")
    reporter_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="提单人名称")
    current_assignee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="当前处理人ID")
    current_assignee_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="当前处理人名称")
    is_problem: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="是否真实问题")
    root_cause: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="最终根因")
    solution: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="最终解决方案")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始处理时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="解决时间")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="关闭时间")
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="首次响应时间")
    total_process_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="总处理耗时秒")
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="标签，建议存储字符串数组")
    extra_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="扩展字段，预留trace、环境、版本等上下文"
    )
    ai_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="AI分析结果预留字段")
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0", comment="删除标志（0存在 2删除）")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketStatusHistory(Base):
    """
    工单状态历史表，记录每个状态阶段的开始、结束和停留耗时。
    """

    __tablename__ = "ticket_status_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="状态历史ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    from_status: Mapped[str] = mapped_column(String(50), nullable=True, comment="原状态")
    to_status: Mapped[str] = mapped_column(String(50), nullable=False, comment="目标状态")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="操作人ID")
    operator_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="操作人名称")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="状态开始时间")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="状态结束时间")
    duration_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="状态停留秒数")
    comment: Mapped[str] = mapped_column(Text, nullable=True, comment="状态流转说明")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketAssignHistory(Base):
    """
    工单指派历史表，记录每次处理人变化和原因。
    """

    __tablename__ = "ticket_assign_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="指派历史ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    from_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="原处理人ID")
    from_user_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="原处理人名称")
    to_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="新处理人ID")
    to_user_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="新处理人名称")
    assigned_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="指派人ID")
    assigned_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="指派人名称")
    reason: Mapped[str] = mapped_column(Text, nullable=True, comment="指派原因")
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="指派时间")


class TicketComment(Base):
    """
    工单评论表，用于沟通记录；结构化排查过程应写入 TicketEvent。
    """

    __tablename__ = "ticket_comment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="评论ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="评论人ID")
    user_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="评论人名称")
    content: Mapped[str] = mapped_column(long_text_type(), nullable=False, comment="评论内容")
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否内部评论")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketMessage(Base):
    """
    工单消息流表，将评论、追问、AI回复和排查动作统一沉淀为可持续会话上下文。
    """

    __tablename__ = "ticket_message"
    __table_args__ = (
        Index("idx_ticket_message_ticket_time", "ticket_id", "create_time"),
        Index("idx_ticket_message_ticket_role", "ticket_id", "role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="消息ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="user", comment="消息角色")
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="comment", comment="消息类型")
    content: Mapped[str] = mapped_column(long_text_type(), nullable=False, comment="消息内容")
    attachments: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="附件或引用信息")
    reference_type: Mapped[str] = mapped_column(String(50), nullable=True, default="", comment="来源对象类型")
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="来源对象ID")
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人ID")
    created_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建人名称")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketEvent(Base):
    """
    工单事件表，统一沉淀时间线、排查记录、修复记录和后续 AI 学习数据。
    """

    __tablename__ = "ticket_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="事件ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, comment="事件类型")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="操作人ID")
    operator_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="操作人名称")
    content: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="事件说明")
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="结构化事件数据")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="事件时间")


class TicketRca(Base):
    """
    工单 RCA 表，结构化保存根因、影响范围、复现步骤、修复和预防方案。
    """

    __tablename__ = "ticket_rca"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="RCA ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True, comment="工单ID")
    symptom: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="问题现象")
    root_cause_category: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="根因分类")
    root_cause_detail: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="根因详情")
    trigger_reason: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="触发原因")
    impact_scope: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="影响范围")
    reproduce_steps: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="复现步骤")
    investigation_process: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="排查过程")
    fix_solution: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="修复方案")
    verify_method: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="验证方式")
    prevention_solution: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="长期预防方案")
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="RCA结构化扩展数据")
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人ID")
    created_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建人名称")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketSnapshot(Base):
    """
    工单 ACR 快照表，记录每次 AI 或人工总结后的当前结论版本。
    """

    __tablename__ = "ticket_snapshot"
    __table_args__ = (
        UniqueConstraint("ticket_id", "version", name="uk_ticket_snapshot_ticket_version"),
        Index("idx_ticket_snapshot_ticket_time", "ticket_id", "create_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="快照ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="快照版本号")
    summary: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="当前摘要")
    root_cause: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="当前根因")
    solution: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="当前解决方案")
    prevention: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="预防建议")
    risk: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="风险说明")
    owner: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="建议负责人")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual", comment="快照来源")
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="来源对象ID")
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="结构化快照数据")
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人ID")
    created_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建人名称")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketAiRepoMapping(Base):
    """
    工单 AI 分析仓库映射表，用于维护项目、版本与仓库分支的对应关系。
    """

    __tablename__ = "ticket_ai_repo_mapping"
    __table_args__ = (
        UniqueConstraint("project_id", "version_key", name="uk_ticket_ai_repo_mapping_project_version"),
        Index("idx_ticket_ai_repo_mapping_project_enabled", "project_id", "enabled"),
    )

    mapping_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="映射ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="项目ID")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="项目名称")
    version_key: Mapped[str] = mapped_column(String(100), nullable=False, comment="版本标识")
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="仓库地址")
    branch_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="分支名称")
    local_repo_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="Worker本地仓库路径")
    workspace_root: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="Worker工作区根目录")
    worker_command: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="Worker执行命令")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否默认映射")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    remark: Mapped[str] = mapped_column(Text, nullable=True, comment="备注")
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="扩展字段")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketAiAnalysisTask(Base):
    """
    工单 AI 分析任务表，记录任务上下文、执行状态、结果和回写信息。
    """

    __tablename__ = "ticket_ai_analysis_task"

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="任务ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="项目ID")
    mapping_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True, comment="仓库映射ID")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="项目名称")
    version_key: Mapped[str] = mapped_column(String(100), nullable=False, default="", comment="版本标识")
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="仓库地址")
    branch_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="分支名称")
    local_repo_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="本地仓库路径")
    workspace_root: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="工作区根目录")
    workspace_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="任务工作区路径")
    prompt_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="提示词文件路径")
    result_path: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="结果文件路径")
    command_line: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="执行命令")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created", comment="任务状态")
    status_desc: Mapped[str] = mapped_column(String(200), nullable=False, default="待执行", comment="状态描述")
    error_message: Mapped[str] = mapped_column(Text, nullable=True, comment="失败信息")
    prompt_text: Mapped[str] = mapped_column(long_text_type(), nullable=False, default="", comment="提示词内容")
    raw_output: Mapped[str] = mapped_column(long_text_type(), nullable=False, default="", comment="AI原始输出")
    analysis_result: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="结构化分析结果")
    analysis_context: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="任务上下文快照")
    source_log_pull_record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="来源日志记录ID")
    source_log_view_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="stored", comment="日志来源模式"
    )
    submitted_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="提交人ID")
    submitted_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="提交人名称")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始执行时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束执行时间")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class KnowledgeArticle(Base):
    """
    知识库文章表，用于沉淀历史问题、解决方案和 RCA 复盘内容。
    """

    __tablename__ = "knowledge_article"

    article_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="知识库文章ID"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="文章标题")
    content: Mapped[str] = mapped_column(long_text_type(), nullable=False, comment="文章内容")
    category: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="文章分类")
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="标签，建议存储字符串数组")
    related_ticket_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="关联工单ID列表")
    embedding_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", comment="向量生成状态")
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="创建人ID")
    created_by_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建人名称")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0", comment="删除标志（0存在 2删除）")


class EmbeddingRecord(Base):
    """
    通用 Embedding 记录表，前期可存 JSON 数组，后续迁移 pgvector/Qdrant 时按模型版本重建索引。
    """

    __tablename__ = "embedding_record"
    __table_args__ = (
        UniqueConstraint(
            "object_type", "object_id", "embedding_model", "embedding_version", name="uk_embedding_object_model_version"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="Embedding ID")
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="对象类型")
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="对象ID")
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False, comment="Embedding模型")
    embedding_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1", comment="Embedding版本")
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, comment="向量维度")
    embedding: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="向量数据，前期JSON数组，后续可迁移向量库"
    )
    content_hash: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="内容哈希")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class WorkflowStatus(Base):
    """
    工单工作流状态表，用于配置状态机节点。
    """

    __tablename__ = "workflow_status"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="状态ID")
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="状态编码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="状态名称")
    is_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否开始状态")
    is_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否结束状态")
    order_num: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class WorkflowTransition(Base):
    """
    工单工作流流转表，用于配置状态允许从哪里流转到哪里。
    """

    __tablename__ = "workflow_transition"
    __table_args__ = (UniqueConstraint("from_status", "to_status", name="uk_workflow_transition_from_to"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="流转ID")
    from_status: Mapped[str] = mapped_column(String(50), nullable=False, comment="原状态")
    to_status: Mapped[str] = mapped_column(String(50), nullable=False, comment="目标状态")
    allowed_roles: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="允许角色编码列表")
    need_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否需要备注")
    need_resolution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否需要解决方案")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketStatisticsDaily(Base):
    """
    工单每日统计表，预留离线聚合结果。
    """

    __tablename__ = "ticket_statistics_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="统计ID")
    statistics_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, comment="统计日期")
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增数量")
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="解决数量")
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关闭数量")
    avg_process_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均处理秒数")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class UserStatisticsDaily(Base):
    """
    用户每日工单统计表，预留处理量和耗时聚合结果。
    """

    __tablename__ = "user_statistics_daily"
    __table_args__ = (UniqueConstraint("statistics_date", "user_id", name="uk_user_statistics_daily_date_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="统计ID")
    statistics_date: Mapped[date] = mapped_column(Date, nullable=False, comment="统计日期")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    user_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="用户名称")
    handled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="处理数量")
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关闭数量")
    avg_process_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均处理秒数")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
