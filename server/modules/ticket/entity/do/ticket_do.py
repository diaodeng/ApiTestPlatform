from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
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
    __table_args__ = (
        Index("idx_ticket_del_status_create", "del_flag", "status", "create_time", "ticket_id"),
        Index(
            "idx_ticket_del_project_module_create",
            "del_flag",
            "project_id",
            "module_id",
            "create_time",
            "ticket_id",
        ),
        Index("idx_ticket_del_current_assignee_create", "del_flag", "current_assignee_id", "create_time", "ticket_id"),
        Index("idx_ticket_del_internal_owner_create", "del_flag", "internal_owner_id", "create_time", "ticket_id"),
        Index("idx_ticket_del_first_line_create", "del_flag", "first_line_assignee_id", "create_time", "ticket_id"),
        Index("idx_ticket_del_issue_type_create", "del_flag", "issue_type_id", "create_time", "ticket_id"),
        Index("idx_ticket_del_problem_pattern_create", "del_flag", "problem_pattern_code", "create_time", "ticket_id"),
        Index("idx_ticket_del_root_cause_create", "del_flag", "root_cause_type", "create_time", "ticket_id"),
        Index("idx_ticket_del_solution_create", "del_flag", "solution_type", "create_time", "ticket_id"),
        Index("idx_ticket_del_resolution_create", "del_flag", "resolution_code", "create_time", "ticket_id"),
        Index("idx_ticket_del_submit_time", "del_flag", "submit_time", "ticket_id"),
        Index("idx_ticket_del_processed_time", "del_flag", "processed_at", "ticket_id"),
        Index("idx_ticket_del_resolved_time", "del_flag", "resolved_at", "ticket_id"),
        Index("idx_ticket_del_closed_time", "del_flag", "closed_at", "ticket_id"),
        Index("idx_ticket_del_affected_version_id", "del_flag", "affected_version_id", "ticket_id"),
        Index("idx_ticket_del_planned_fix_version_id", "del_flag", "planned_fix_version_id", "ticket_id"),
        Index("idx_ticket_del_fixed_version_id", "del_flag", "fixed_version_id", "ticket_id"),
        Index("idx_ticket_del_released_version_id", "del_flag", "released_version_id", "ticket_id"),
        Index("idx_ticket_del_issue", "del_flag", "issue_id", "ticket_id"),
    )

    ticket_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, unique=True, default=snowIdWorker.get_id, comment="工单ID"
    )
    ticket_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="工单编号")
    ticket_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="工单详情链接")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="工单标题")
    description: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="工单描述")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属项目ID")
    merchant_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="所属商家")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属模块ID")
    module_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="所属模块名称")
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="问题分类ID")
    category_name: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="问题分类名称")
    issue_type_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default="", comment="工单类型编码")
    issue_type_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="工单类型名称")
    classification_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="工单类型分类来源：manual/external_mapping/ai"
    )
    classification_rule_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="外部字段分类规则ID"
    )
    classification_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="工单类型分类更新时间")
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
    first_line_assignee_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="1线人员ID")
    first_line_assignee_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="1线人员名称")
    internal_owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="内部工单负责人ID")
    internal_owner_name: Mapped[str] = mapped_column(
        String(100), nullable=True, default="", comment="内部工单负责人名称"
    )
    is_problem: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="是否真实问题")
    root_cause_type: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="根因分类")
    solution_type: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="解决方式")
    resolution_code: Mapped[str | None] = mapped_column(String(64), nullable=True, default="", comment="关闭结果编码")
    resolution_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="关闭结果名称")
    problem_pattern_code: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="", comment="细分问题类型编码"
    )
    problem_pattern_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True, default="", comment="细分问题类型名称"
    )
    problem_pattern_confidence: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="细分问题类型置信度，0-100"
    )
    problem_pattern_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="", comment="细分问题类型来源"
    )
    problem_pattern_verified: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="细分问题类型是否人工确认"
    )
    problem_pattern_verified_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="", comment="细分问题类型确认人"
    )
    problem_pattern_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="细分问题类型确认时间"
    )
    issue_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="归属问题实例ID")
    issue_relation_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="", comment="问题实例归属类型，如 primary/similar/manual"
    )
    issue_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="问题归因是否人工确认"
    )
    affected_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="发生版本中心ID")
    planned_fix_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="计划修复版本中心ID")
    fixed_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="实际修复版本中心ID")
    released_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="实际发版版本中心ID")
    root_cause: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="最终根因")
    solution: Mapped[str] = mapped_column(long_text_type(), nullable=True, comment="最终解决方案")
    submit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="工单业务提交时间")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始处理时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="处置完成时间")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="关闭时间")
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="首次响应时间")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="首次形成处理结论时间")
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="实际发版时间")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="验证完成时间")
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


class TicketIssue(Base):
    """
    真实问题实例主表，用于承载多张工单归属到同一个业务问题的主归因口径。
    """

    __tablename__ = "ticket_issue"
    __table_args__ = (
        UniqueConstraint("issue_no", name="uk_ticket_issue_no"),
        Index("idx_ticket_issue_del_status_update", "del_flag", "status", "update_time", "issue_id"),
        Index("idx_ticket_issue_del_project_module", "del_flag", "project_id", "module_id", "issue_id"),
        Index("idx_ticket_issue_del_pattern", "del_flag", "problem_pattern_code", "issue_id"),
    )

    issue_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment="问题实例ID"
    )
    issue_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="问题实例编号")
    title: Mapped[str] = mapped_column(String(500), nullable=False, comment="问题标题")
    summary: Mapped[str | None] = mapped_column(long_text_type(), nullable=True, comment="问题摘要")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", comment="问题状态")
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True, default="", comment="严重等级")
    project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属项目ID")
    project_name: Mapped[str | None] = mapped_column(String(200), nullable=True, default="", comment="所属项目名称")
    module_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="所属模块ID")
    module_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="所属模块名称")
    root_cause_type: Mapped[str | None] = mapped_column(String(128), nullable=True, default="", comment="根因分类")
    problem_pattern_code: Mapped[str | None] = mapped_column(
        String(128), nullable=True, default="", comment="细分问题类型编码"
    )
    problem_pattern_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True, default="", comment="细分问题类型名称"
    )
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="负责人ID")
    owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True, default="", comment="负责人名称")
    first_ticket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="首张工单ID")
    affected_ticket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="影响工单数")
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0", comment="删除标志（0存在 2删除）")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketRelation(Base):
    """
    工单补充关系表，仅记录工单间相似、重复、关联等辅助关系，不替代 ticket.issue_id 主归因。
    """

    __tablename__ = "ticket_relation"
    __table_args__ = (
        UniqueConstraint("source_ticket_id", "target_ticket_id", "relation_type", name="uk_ticket_relation_pair_type"),
        Index("idx_ticket_relation_source", "source_ticket_id", "relation_type", "del_flag"),
        Index("idx_ticket_relation_target", "target_ticket_id", "relation_type", "del_flag"),
    )

    relation_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, nullable=False, default=snowIdWorker.get_id, comment="关系ID"
    )
    source_ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="源工单ID")
    target_ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="目标工单ID")
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="similar", comment="关系类型")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, comment="关系置信度，0-1")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="关系来源")
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否人工确认")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    del_flag: Mapped[str] = mapped_column(String(1), nullable=False, default="0", comment="删除标志（0存在 2删除）")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


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
    __table_args__ = (
        UniqueConstraint("ticket_id", "source_segment_key", name="uk_ticket_comment_source_segment"),
        Index("idx_ticket_comment_source", "source_type", "source_record_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="评论ID")
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="工单ID")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="评论人ID")
    user_name: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="评论人名称")
    content: Mapped[str] = mapped_column(long_text_type(), nullable=False, comment="评论内容")
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否内部评论")
    attachments: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="评论附件或引用信息")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="local", comment="评论来源类型")
    source_system: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="外部来源系统")
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="外部来源记录ID")
    source_field: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="外部来源字段")
    source_segment_key: Mapped[str | None] = mapped_column(String(256), nullable=True, comment="外部评论分段幂等键")
    source_segment_index: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="外部分段序号")
    source_content_hash: Mapped[str] = mapped_column(String(128), nullable=True, default="", comment="外部内容哈希")
    external_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="外部评论时间")
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


class TicketVersion(Base):
    """
    项目版本主数据，统一承接人工维护和工单自动发现的版本。
    """

    __tablename__ = "ticket_version"
    __table_args__ = (
        UniqueConstraint("project_id", "version_key", name="uk_ticket_version_project_key"),
        Index("idx_ticket_version_project_status", "project_id", "lifecycle_status", "enabled"),
    )

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="版本ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="所属项目ID")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="所属项目名称")
    version_key: Mapped[str] = mapped_column(String(100), nullable=False, comment="规范化版本标识")
    version_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="版本展示名称")
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="discovered", comment="版本状态：discovered/confirmed/deprecated"
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="首次来源")
    raw_version: Mapped[str] = mapped_column(String(200), nullable=True, default="", comment="首次发现原始版本文本")
    first_ticket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="首次发现工单ID")
    first_detected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="首次发现时间")
    planned_release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="计划发布时间")
    default_branch: Mapped[str] = mapped_column(String(200), nullable=True, default="", comment="默认代码分支")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否可选")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketVersionRelease(Base):
    """
    版本在各环境的发布事实记录，支持同一版本多次发布与回滚审计。
    """

    __tablename__ = "ticket_version_release"
    __table_args__ = (
        UniqueConstraint("version_id", "environment", "batch_no", name="uk_ticket_version_release_batch"),
        Index("idx_ticket_version_release_version_time", "version_id", "released_at"),
    )

    release_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="发布记录ID"
    )
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="版本ID")
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="production", comment="发布环境")
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, default="default", comment="发布批次")
    release_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="planned", comment="发布状态：planned/released/rolled_back"
    )
    planned_release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="计划发布时间")
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="实际发布时间")
    rollback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="回滚时间")
    release_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="发布人")
    ci_url: Mapped[str] = mapped_column(String(1000), nullable=True, default="", comment="CI/CD 链接")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="发布说明")
    create_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="创建者")
    update_by: Mapped[str] = mapped_column(String(100), nullable=True, default="", comment="更新者")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )


class TicketAiRepoMapping(Base):
    """
    工单 AI 分析仓库映射表，用于维护项目、版本与仓库分支的对应关系。
    """

    __tablename__ = "ticket_ai_repo_mapping"
    __table_args__ = (
        UniqueConstraint("project_id", "version_id", name="uk_ticket_ai_repo_mapping_project_version"),
        Index("idx_ticket_ai_repo_mapping_project_enabled", "project_id", "enabled"),
    )

    mapping_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="映射ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="项目ID")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="项目名称")
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="版本中心ID")
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
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="版本中心ID")
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
    工单每日统计表，按自然日冻结工单处理口径汇总结果。
    """

    __tablename__ = "ticket_statistics_daily"
    __table_args__ = (
        UniqueConstraint(
            "statistics_date",
            "snapshot_scope",
            "project_id",
            "module_id",
            "issue_type_id",
            name="uk_ticket_statistics_daily_scope",
        ),
        Index("idx_ticket_statistics_daily_date", "statistics_date"),
        Index("idx_ticket_statistics_daily_scope_date", "snapshot_scope", "statistics_date"),
        Index("idx_ticket_statistics_daily_project", "statistics_date", "project_id"),
        Index("idx_ticket_statistics_daily_module", "statistics_date", "module_id", "module_code"),
        Index("idx_ticket_statistics_daily_issue_type", "statistics_date", "issue_type_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="统计ID")
    statistics_date: Mapped[date] = mapped_column(Date, nullable=False, comment="统计日期")
    snapshot_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", comment="快照范围：all全局，leaf项目模块问题类型明细"
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="项目ID，0表示全局或未归属")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="项目名称快照")
    module_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="模块ID，0表示全局或未归属")
    module_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="模块名称快照")
    module_code: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="模块业务码快照")
    issue_type_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="工单类型编码，空表示全局或未填写"
    )
    issue_type_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="工单类型名称快照")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="工单总数")
    submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数")
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数（兼容旧字段）")
    first_responded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已响应数")
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已处理数")
    processed_in_new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单已处理数")
    process_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="新增工单处理率")
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="处置完成数")
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关闭数")
    unprocessed_backlog: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="周期末未处理存量")
    open_backlog: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="周期末未关闭存量")
    avg_first_response_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均首次响应耗时"
    )
    avg_first_process_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均首次处理耗时"
    )
    avg_resolve_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均处置完成耗时")
    avg_close_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均关闭耗时")
    avg_process_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均处理秒数（旧字段，兼容保留）"
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketStatisticsPeriodSnapshot(Base):
    """
    工单周期统计快照表，用于冻结非自然日周期，例如周四 18:00 开始的业务周。
    """

    __tablename__ = "ticket_statistics_period_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "period_type",
            "period_start_time",
            "snapshot_scope",
            "project_id",
            "module_id",
            "issue_type_id",
            name="uk_ticket_statistics_period_scope",
        ),
        Index("idx_ticket_statistics_period_start", "period_type", "period_start_time"),
        Index("idx_ticket_statistics_period_scope_start", "snapshot_scope", "period_type", "period_start_time"),
        Index("idx_ticket_statistics_period_project", "period_start_time", "project_id"),
        Index("idx_ticket_statistics_period_module", "period_start_time", "module_id", "module_code"),
        Index("idx_ticket_statistics_period_issue_type", "period_start_time", "issue_type_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="统计ID")
    period_type: Mapped[str] = mapped_column(String(32), nullable=False, default="business_week", comment="周期类型")
    period_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="周期键，如业务周开始日期")
    period_start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="周期开始时间")
    period_end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="周期结束时间")
    snapshot_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", comment="快照范围：all全局，leaf项目模块问题类型明细"
    )
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="项目ID，0表示全局或未归属")
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="项目名称快照")
    module_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="模块ID，0表示全局或未归属")
    module_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="模块名称快照")
    module_code: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="模块业务码快照")
    issue_type_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="工单类型编码，空表示全局或未填写"
    )
    issue_type_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="工单类型名称快照")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="工单总数")
    submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数")
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单数（兼容旧字段）")
    first_responded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已响应数")
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已处理数")
    processed_in_new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="新增工单已处理数")
    process_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment="新增工单处理率")
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="处置完成数")
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="关闭数")
    unprocessed_backlog: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="周期末未处理存量")
    open_backlog: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="周期末未关闭存量")
    avg_first_response_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均首次响应耗时"
    )
    avg_first_process_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均首次处理耗时"
    )
    avg_resolve_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均处置完成耗时")
    avg_close_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="平均关闭耗时")
    avg_process_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="平均处理秒数（旧字段，兼容保留）"
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TicketStatisticsMetricSnapshot(Base):
    """工单可配置趋势指标快照，按日或业务周覆盖写入。"""

    __tablename__ = "ticket_statistics_metric_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_type", "snapshot_key", "snapshot_scope", "project_id", "module_id",
            "issue_type_id", "metric_code", "group_code", name="uk_ticket_metric_snapshot_scope"
        ),
        Index("idx_ticket_metric_snapshot_time", "snapshot_type", "snapshot_key"),
        Index("idx_ticket_metric_snapshot_metric", "metric_code", "snapshot_type", "snapshot_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=snowIdWorker.get_id, comment="指标快照ID")
    snapshot_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="快照类型：daily/business_week")
    snapshot_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="快照日期或业务周开始日期")
    snapshot_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="all", comment="快照范围：all/leaf")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="项目ID")
    module_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="模块ID")
    issue_type_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="工单类型编码")
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="自定义指标编码")
    metric_label: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="自定义指标名称")
    group_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="指标分组编码")
    group_label: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="指标分组名称")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="命中数量")
    definition_revision: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="指标定义版本")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")


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
