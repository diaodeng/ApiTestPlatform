from datetime import date, datetime, time
from typing import Any

from sqlalchemy import DateTime as SqlDateTime
from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.orm import Session

from module_admin.entity.do.user_do import SysUser
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.enums.enums import QtrDataStatusEnum
from modules.ticket.entity.do.ticket_do import (
    EmbeddingRecord,
    KnowledgeArticle,
    Ticket,
    TicketAiAnalysisTask,
    TicketAssignHistory,
    TicketComment,
    TicketEvent,
    TicketMessage,
    TicketRca,
    TicketSnapshot,
    TicketStatusHistory,
    WorkflowStatus,
    WorkflowTransition,
)
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.vo.ticket_vo import KnowledgeArticleQueryModel, TicketQueryModel
from utils.page_util import PageUtil


def _date_start(value: date | datetime | str | None) -> datetime | None:
    """
    将日期查询参数转换为开始时间。
    :param value: 日期、时间或字符串
    :return: 当天开始时间
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.combine(date.fromisoformat(str(value)[:10]), time.min)


def _date_end(value: date | datetime | str | None) -> datetime | None:
    """
    将日期查询参数转换为结束时间。
    :param value: 日期、时间或字符串
    :return: 当天结束时间
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.max)
    return datetime.combine(date.fromisoformat(str(value)[:10]), time.max)


def _parse_sync_time(value: Any) -> datetime | None:
    """
    解析同步元数据时间。
    :param value: ISO 时间字符串或 datetime 对象
    :return: 可比较的 datetime，解析失败返回 None
    """
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _json_safe_value(value: Any) -> Any:
    """
    将值递归转换为可 JSON 序列化内容。
    :param value: 原始值
    :return: 可被 JSON 序列化的值
    """
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, set):
        return [_json_safe_value(item) for item in value]
    if hasattr(value, "__table__"):
        return {
            column.name: _json_safe_value(getattr(value, column.name))
            for column in value.__table__.columns
        }
    if hasattr(value, "model_dump"):
        try:
            return _json_safe_value(value.model_dump(by_alias=False, exclude_none=False))
        except Exception:
            return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _latest_log_pull_status_expr(ticket_id_column):
    """
    构造工单最新日志拉取状态的关联子查询表达式。
    :param ticket_id_column: 工单ID列
    :return: 状态子查询
    """
    return (
        select(TicketLogPullRecord.status)
        .where(TicketLogPullRecord.ticket_id == ticket_id_column)
        .order_by(TicketLogPullRecord.create_time.desc(), TicketLogPullRecord.id.desc())
        .limit(1)
        .scalar_subquery()
    )


def _latest_ai_status_expr(ticket_id_column):
    """
    构造工单最新 AI 分析状态的关联子查询表达式。
    :param ticket_id_column: 工单ID列
    :return: 状态子查询
    """
    return (
        select(TicketAiAnalysisTask.status)
        .where(TicketAiAnalysisTask.ticket_id == ticket_id_column)
        .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
        .limit(1)
        .scalar_subquery()
    )


def _ticket_submit_time_expr():
    """
    构造工单提交时间表达式（外部 createTime 优先，缺失时回退本地 create_time）。
    :return: 可用于 SQL 查询过滤的提交时间表达式
    """
    external_create_time_expr = Ticket.extra_data["external_sync"]["externalCreateTime"].as_string()
    source_external_create_time_expr = Ticket.extra_data["external_sync"]["source"]["externalCreateTime"].as_string()
    resolved_external_create_time_expr = func.coalesce(
        func.nullif(external_create_time_expr, ""),
        func.nullif(source_external_create_time_expr, ""),
    )
    return func.coalesce(cast(resolved_external_create_time_expr, SqlDateTime), Ticket.create_time)


def _build_ticket_process_status_filter(latest_log_status, latest_ai_status, process_status: str):
    """
    根据工单处理状态构造过滤条件。
    :param latest_log_status: 最新日志拉取状态表达式
    :param latest_ai_status: 最新 AI 分析状态表达式
    :param process_status: 处理状态编码
    :return: 过滤条件表达式
    """
    if process_status == "no_log_pull":
        return latest_log_status.is_(None)
    if process_status in {
        "log_pull_created",
        "log_pull_submitting",
        "log_pull_polling",
        "log_pull_downloading",
        "log_pull_processing",
    }:
        return latest_log_status == process_status.replace("log_pull_", "", 1)
    if process_status == "log_pull_running":
        return latest_log_status.in_(["created", "submitting", "polling", "downloading", "processing"])
    if process_status == "log_pull_success":
        return latest_log_status == "success"
    if process_status == "log_pull_failed":
        return latest_log_status.in_(["failed", "exception"])
    if process_status == "ai_not_analyzed":
        return and_(latest_log_status == "success", latest_ai_status.is_(None))
    if process_status == "ai_running":
        return and_(latest_log_status == "success", latest_ai_status.in_(["created", "running"]))
    if process_status == "ai_success":
        return latest_ai_status == "success"
    if process_status == "ai_failed":
        return latest_ai_status.in_(["failed", "canceled"])
    return True


def _resolve_module_ids_by_codes(
    db: Session,
    module_codes: list[str],
    project_ids: list[int] | None = None,
) -> list[int]:
    """
    根据模块业务码解析模块ID列表，支持按项目范围收敛。
    :param db: 数据库会话
    :param module_codes: 模块业务码列表
    :param project_ids: 可选项目ID列表
    :return: 命中的模块ID列表
    """
    normalized_codes = [str(item or "").strip() for item in module_codes if str(item or "").strip()]
    if not normalized_codes:
        return []
    query = db.query(HrmModule.module_id).filter(
        HrmModule.status == QtrDataStatusEnum.normal.value,
        HrmModule.module_code.in_(normalized_codes),
    )
    if project_ids:
        query = query.filter(HrmModule.project_id.in_(project_ids))
    return [row[0] for row in query.distinct().all() if row[0]]


class TicketDao:
    """
    工单模块数据库访问层。
    """

    @classmethod
    def get_ticket_by_id(cls, db: Session, ticket_id: int) -> Ticket | None:
        """
        根据工单ID获取未删除工单。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 工单对象
        """
        return db.query(Ticket).filter(Ticket.ticket_id == ticket_id, Ticket.del_flag == "0").first()

    @classmethod
    def get_ticket_by_no(cls, db: Session, ticket_no: str) -> Ticket | None:
        """
        根据工单编号获取未删除工单。
        :param db: 数据库会话
        :param ticket_no: 工单编号
        :return: 工单对象
        """
        return db.query(Ticket).filter(Ticket.ticket_no == ticket_no, Ticket.del_flag == "0").first()

    @classmethod
    def get_existing_ticket_nos(cls, db: Session, ticket_nos: list[str]) -> set[str]:
        """
        批量查询已存在的工单编号。
        :param db: 数据库会话
        :param ticket_nos: 工单编号列表
        :return: 已存在工单编号集合
        """
        if not ticket_nos:
            return set()
        rows = (
            db.query(Ticket.ticket_no)
            .filter(Ticket.ticket_no.in_(ticket_nos))
            .all()
        )
        return {row[0] for row in rows}

    @classmethod
    def get_ticket_list(cls, db: Session, query: TicketQueryModel):
        """
        根据查询条件分页获取工单列表。
        :param db: 数据库会话
        :param query: 工单查询参数
        :return: 分页结果或列表
        """
        begin_time = _date_start(query.begin_time)
        end_time = _date_end(query.end_time)
        submit_begin_time = _date_start(query.submit_begin_time)
        submit_end_time = _date_end(query.submit_end_time)
        ticket_no = str(query.ticket_no or "").strip()
        process_status = str(query.process_status or "").strip()
        module_code = str(query.module_code or "").strip()
        latest_log_status = _latest_log_pull_status_expr(Ticket.ticket_id)
        latest_ai_status = _latest_ai_status_expr(Ticket.ticket_id)
        submit_time_expr = _ticket_submit_time_expr()
        matched_module_ids_by_code = (
            _resolve_module_ids_by_codes(
                db,
                [module_code],
                [query.project_id] if query.project_id else None,
            )
            if module_code
            else []
        )
        ticket_query = (
            db.query(Ticket)
            .filter(
                Ticket.del_flag == "0",
                Ticket.ticket_no.like(f"%{ticket_no}%") if ticket_no else True,
                Ticket.title.like(f"%{query.title}%") if query.title else True,
                Ticket.status == query.status if query.status else True,
                Ticket.project_id == query.project_id if query.project_id else True,
                Ticket.module_id == query.module_id if query.module_id else True,
                Ticket.module_id.in_(matched_module_ids_by_code) if module_code and matched_module_ids_by_code else (
                    Ticket.ticket_id == -1 if module_code else True
                ),
                Ticket.category_id == query.category_id if query.category_id else True,
                Ticket.issue_type_id == query.issue_type_id if query.issue_type_id else True,
                Ticket.issue_type_name.like(f"%{query.issue_type_name}%") if query.issue_type_name else True,
                Ticket.is_problem == query.is_problem if query.is_problem is not None else True,
                Ticket.root_cause_type == query.root_cause_type if query.root_cause_type else True,
                Ticket.solution_type == query.solution_type if query.solution_type else True,
                Ticket.resolution_code == query.resolution_code if query.resolution_code else True,
                Ticket.resolution_name.like(f"%{query.resolution_name}%") if query.resolution_name else True,
                Ticket.customer_priority == query.customer_priority if query.customer_priority else True,
                Ticket.internal_priority == query.internal_priority if query.internal_priority else True,
                Ticket.source == query.source if query.source else True,
                Ticket.current_assignee_id == query.current_assignee_id if query.current_assignee_id else True,
                Ticket.current_assignee_name.like(f"%{query.current_assignee_name}%")
                if query.current_assignee_name
                else True,
                Ticket.first_line_assignee_id == query.first_line_assignee_id
                if query.first_line_assignee_id
                else True,
                Ticket.first_line_assignee_name.like(f"%{query.first_line_assignee_name}%")
                if query.first_line_assignee_name
                else True,
                Ticket.internal_owner_id == query.internal_owner_id if query.internal_owner_id else True,
                Ticket.internal_owner_name.like(f"%{query.internal_owner_name}%")
                if query.internal_owner_name
                else True,
                Ticket.reporter_id == query.reporter_id if query.reporter_id else True,
                Ticket.create_time >= begin_time if begin_time else True,
                Ticket.create_time <= end_time if end_time else True,
                submit_time_expr >= submit_begin_time if submit_begin_time else True,
                submit_time_expr <= submit_end_time if submit_end_time else True,
            )
            .filter(_build_ticket_process_status_filter(latest_log_status, latest_ai_status, process_status))
            .filter(
                or_(
                    Ticket.title.like(f"%{query.keyword}%"),
                    Ticket.description.like(f"%{query.keyword}%"),
                    Ticket.root_cause.like(f"%{query.keyword}%"),
                    Ticket.solution.like(f"%{query.keyword}%"),
                )
                if query.keyword
                else True
            )
            .order_by(Ticket.create_time.desc())
        )
        return PageUtil.paginate(ticket_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def get_tickets_for_sync(
        cls,
        db: Session,
        *,
        consumer: str,
        limit: int = 50,
        include_closed: bool = True,
    ) -> list[Ticket]:
        """
        按消费者拉取未同步或存在新版本的工单。
        :param db: 数据库会话
        :param consumer: 消费者标识
        :param limit: 最大返回条数
        :param include_closed: 是否包含结束状态工单
        :return: 待同步工单列表
        """
        safe_limit = min(max(int(limit or 50), 1), 200)
        query = db.query(Ticket).filter(Ticket.del_flag == "0")
        if not include_closed:
            query = query.filter(
                ~Ticket.status.in_(
                    [
                        "closed",
                        "rejected",
                        "non_problem",
                        "design_as_expected",
                        "user_misoperation",
                        "duplicated",
                    ]
                )
            )
        result: list[Ticket] = []
        consumer_key = str(consumer or "").strip()
        pulled_retry_seconds = 30 * 60
        now = datetime.now()
        scan_offset = 0
        scan_limit = max(safe_limit * 4, 200)
        ordered_query = query.order_by(Ticket.update_time.asc(), Ticket.create_time.asc())
        while len(result) < safe_limit:
            rows = ordered_query.offset(scan_offset).limit(scan_limit).all()
            if not rows:
                break
            scan_offset += len(rows)
            for ticket in rows:
                extra_data = ticket.extra_data if isinstance(ticket.extra_data, dict) else {}
                sync_meta = extra_data.get("external_sync") if isinstance(extra_data.get("external_sync"), dict) else {}
                state = sync_meta.get("sync_state") if isinstance(sync_meta.get("sync_state"), dict) else {}
                publish_status = str(state.get("publish_status") or "").strip()
                if not bool(state.get("publish_ready", True)) and publish_status != "processing_ai":
                    continue
                consumers = state.get("consumers") if isinstance(state.get("consumers"), dict) else {}
                consumer_state = consumers.get(consumer_key) if isinstance(consumers.get(consumer_key), dict) else {}
                current_revision = int(sync_meta.get("revision") or 0)
                delivered_revision = int(consumer_state.get("delivered_revision") or 0)
                consumer_status = str(consumer_state.get("status") or "").strip().lower()
                last_revision = int(consumer_state.get("last_revision") or 0)
                last_pulled_at = _parse_sync_time(consumer_state.get("delivered_at") or state.get("last_pulled_at"))
                pulled_active = (
                    consumer_status == "pulled"
                    and last_revision == current_revision
                    and last_pulled_at is not None
                    and (now - last_pulled_at).total_seconds() < pulled_retry_seconds
                )
                pulled_expired = (
                    consumer_status == "pulled"
                    and last_revision == current_revision
                    and (
                        last_pulled_at is None
                        or (now - last_pulled_at).total_seconds() >= pulled_retry_seconds
                    )
                )
                should_return_ticket = (delivered_revision < current_revision and not pulled_active) or pulled_expired
                if current_revision > 0 and should_return_ticket:
                    result.append(ticket)
                if len(result) >= safe_limit:
                    break
            if len(rows) < scan_limit:
                break
        return result

    @classmethod
    def add_ticket(cls, db: Session, ticket: Ticket) -> Ticket:
        """
        新增工单。
        :param db: 数据库会话
        :param ticket: 工单对象
        :return: 新增后的工单对象
        """
        db.add(ticket)
        db.flush()
        return ticket

    @classmethod
    def get_tickets_by_ids(cls, db: Session, ticket_ids: list[int]) -> list[Ticket]:
        """
        根据工单ID列表查询未删除工单。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 工单列表
        """
        if not ticket_ids:
            return []
        return db.query(Ticket).filter(Ticket.del_flag == "0", Ticket.ticket_id.in_(ticket_ids)).all()

    @classmethod
    def update_ticket(cls, db: Session, ticket_id: int, data: dict) -> None:
        """
        更新工单字段。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param data: 待更新字段
        :return: 无
        """
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).update(data)

    @classmethod
    def delete_ticket(cls, db: Session, ticket_id: int, data: dict) -> None:
        """
        软删除工单。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param data: 删除标记和审计字段
        :return: 无
        """
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).update(data)

    @classmethod
    def add_status_history(cls, db: Session, history: TicketStatusHistory) -> TicketStatusHistory:
        """
        新增状态历史。
        :param db: 数据库会话
        :param history: 状态历史对象
        :return: 状态历史对象
        """
        db.add(history)
        db.flush()
        return history

    @classmethod
    def close_open_status_history(cls, db: Session, ticket_id: int, ended_at: datetime) -> None:
        """
        关闭当前未结束的状态历史并写入停留时长。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param ended_at: 结束时间
        :return: 无
        """
        current = (
            db.query(TicketStatusHistory)
            .filter(TicketStatusHistory.ticket_id == ticket_id, TicketStatusHistory.ended_at.is_(None))
            .order_by(TicketStatusHistory.started_at.desc())
            .first()
        )
        if current:
            current.ended_at = ended_at
            current.duration_seconds = max(int((ended_at - current.started_at).total_seconds()), 0)

    @classmethod
    def add_assign_history(cls, db: Session, history: TicketAssignHistory) -> TicketAssignHistory:
        """
        新增指派历史。
        :param db: 数据库会话
        :param history: 指派历史对象
        :return: 指派历史对象
        """
        db.add(history)
        db.flush()
        return history

    @classmethod
    def add_comment(cls, db: Session, comment: TicketComment) -> TicketComment:
        """
        新增评论。
        :param db: 数据库会话
        :param comment: 评论对象
        :return: 评论对象
        """
        if comment.attachments is not None:
            comment.attachments = _json_safe_value(comment.attachments)
        db.add(comment)
        db.flush()
        return comment

    @classmethod
    def list_comments(cls, db: Session, ticket_id: int) -> list[TicketComment]:
        """
        查询工单评论列表。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 按创建时间升序排列的评论列表
        """
        return (
            db.query(TicketComment)
            .filter(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.create_time.asc(), TicketComment.id.asc())
            .all()
        )

    @classmethod
    def get_comment_by_source_segment_key(
        cls,
        db: Session,
        *,
        ticket_id: int,
        source_segment_key: str,
    ) -> TicketComment | None:
        """
        根据外部评论分段幂等键查询评论。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param source_segment_key: 外部评论分段幂等键
        :return: 评论对象或 None
        """
        normalized_key = str(source_segment_key or "").strip()
        if not normalized_key:
            return None
        return (
            db.query(TicketComment)
            .filter(
                TicketComment.ticket_id == ticket_id,
                TicketComment.source_segment_key == normalized_key,
            )
            .first()
        )

    @classmethod
    def get_comment_by_source_content_hash(
        cls,
        db: Session,
        *,
        ticket_id: int,
        source_content_hash: str,
    ) -> TicketComment | None:
        """
        根据外部评论内容哈希查询评论，用于跨来源回流去重。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param source_content_hash: 外部评论内容哈希
        :return: 评论对象或 None
        """
        normalized_hash = str(source_content_hash or "").strip()
        if not normalized_hash:
            return None
        return (
            db.query(TicketComment)
            .filter(
                TicketComment.ticket_id == ticket_id,
                TicketComment.source_content_hash == normalized_hash,
            )
            .first()
        )

    @classmethod
    def update_comment(cls, db: Session, comment_id: int, data: dict[str, Any]) -> None:
        """
        更新评论字段。
        :param db: 数据库会话
        :param comment_id: 评论ID
        :param data: 待更新字段
        :return: 无
        """
        if "attachments" in data and data["attachments"] is not None:
            data["attachments"] = _json_safe_value(data["attachments"])
        db.query(TicketComment).filter(TicketComment.id == comment_id).update(data)

    @classmethod
    def update_message_by_reference(
        cls,
        db: Session,
        *,
        reference_type: str,
        reference_id: int,
        data: dict[str, Any],
    ) -> None:
        """
        按来源对象更新消息流内容。
        :param db: 数据库会话
        :param reference_type: 来源对象类型
        :param reference_id: 来源对象ID
        :param data: 待更新字段
        :return: 无
        """
        if "attachments" in data and data["attachments"] is not None:
            data["attachments"] = _json_safe_value(data["attachments"])
        db.query(TicketMessage).filter(
            TicketMessage.reference_type == reference_type,
            TicketMessage.reference_id == reference_id,
        ).update(data)

    @classmethod
    def add_message(cls, db: Session, message: TicketMessage) -> TicketMessage:
        """
        新增工单消息。
        :param db: 数据库会话
        :param message: 消息对象
        :return: 保存后的消息对象
        """
        if message.attachments is not None:
            message.attachments = _json_safe_value(message.attachments)
        db.add(message)
        db.flush()
        return message

    @classmethod
    def list_messages(cls, db: Session, ticket_id: int, limit: int | None = None) -> list[TicketMessage]:
        """
        查询工单消息流。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param limit: 返回最近消息数量；为空时返回全部
        :return: 消息列表
        """
        query = (
            db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.create_time.desc(), TicketMessage.id.desc())
        )
        if limit:
            return list(reversed(query.limit(limit).all()))
        return (
            db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.create_time.asc(), TicketMessage.id.asc())
            .all()
        )

    @classmethod
    def add_snapshot(cls, db: Session, snapshot: TicketSnapshot) -> TicketSnapshot:
        """
        新增工单 ACR 快照。
        :param db: 数据库会话
        :param snapshot: 快照对象
        :return: 保存后的快照对象
        """
        if snapshot.structured_data is not None:
            snapshot.structured_data = _json_safe_value(snapshot.structured_data)
        db.add(snapshot)
        db.flush()
        return snapshot

    @classmethod
    def get_next_snapshot_version(cls, db: Session, ticket_id: int) -> int:
        """
        获取工单下一个快照版本号。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 下一个版本号
        """
        latest_version = (
            db.query(func.max(TicketSnapshot.version))
            .filter(TicketSnapshot.ticket_id == ticket_id)
            .scalar()
            or 0
        )
        return int(latest_version) + 1

    @classmethod
    def list_snapshots(cls, db: Session, ticket_id: int, limit: int | None = None) -> list[TicketSnapshot]:
        """
        查询工单快照列表。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param limit: 返回最近快照数量；为空时返回全部
        :return: 快照列表
        """
        query = (
            db.query(TicketSnapshot)
            .filter(TicketSnapshot.ticket_id == ticket_id)
            .order_by(TicketSnapshot.version.desc(), TicketSnapshot.create_time.desc())
        )
        if limit:
            return query.limit(limit).all()
        return query.all()

    @classmethod
    def get_latest_snapshot(cls, db: Session, ticket_id: int) -> TicketSnapshot | None:
        """
        查询工单最新 ACR 快照。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 最新快照
        """
        return (
            db.query(TicketSnapshot)
            .filter(TicketSnapshot.ticket_id == ticket_id)
            .order_by(TicketSnapshot.version.desc(), TicketSnapshot.create_time.desc())
            .first()
        )

    @classmethod
    def add_event(cls, db: Session, event: TicketEvent) -> TicketEvent:
        """
        新增工单事件。
        :param db: 数据库会话
        :param event: 事件对象
        :return: 事件对象
        """
        if event.event_data is not None:
            event.event_data = _json_safe_value(event.event_data)
        db.add(event)
        db.flush()
        return event

    @classmethod
    def get_timeline(cls, db: Session, ticket_id: int, include_comments: bool = True) -> dict:
        """
        获取工单时间线相关数据。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param include_comments: 是否包含评论；前端历史页按需独立拉取评论时传 False
        :return: 状态历史、指派历史、评论、事件和 RCA
        """
        result = {
            "status_history": db.query(TicketStatusHistory)
            .filter(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.started_at.asc())
            .all(),
            "assign_history": db.query(TicketAssignHistory)
            .filter(TicketAssignHistory.ticket_id == ticket_id)
            .order_by(TicketAssignHistory.assigned_at.asc())
            .all(),
            "events": db.query(TicketEvent)
            .filter(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.create_time.asc())
            .all(),
            "messages": db.query(TicketMessage)
            .filter(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.create_time.asc(), TicketMessage.id.asc())
            .all(),
            "snapshots": db.query(TicketSnapshot)
            .filter(TicketSnapshot.ticket_id == ticket_id)
            .order_by(TicketSnapshot.version.desc(), TicketSnapshot.create_time.desc())
            .all(),
            "rca": db.query(TicketRca).filter(TicketRca.ticket_id == ticket_id).first(),
        }
        if include_comments:
            result["comments"] = cls.list_comments(db, ticket_id)
        return result

    @classmethod
    def get_transition(cls, db: Session, from_status: str, to_status: str) -> WorkflowTransition | None:
        """
        查询状态流转配置。
        :param db: 数据库会话
        :param from_status: 原状态
        :param to_status: 目标状态
        :return: 流转配置
        """
        return (
            db.query(WorkflowTransition)
            .filter(WorkflowTransition.from_status == from_status, WorkflowTransition.to_status == to_status)
            .first()
        )

    @classmethod
    def list_workflow_status(cls, db: Session) -> list[WorkflowStatus]:
        """
        查询工作流状态列表。
        :param db: 数据库会话
        :return: 状态列表
        """
        return db.query(WorkflowStatus).order_by(WorkflowStatus.order_num.asc(), WorkflowStatus.create_time.asc()).all()

    @classmethod
    def get_workflow_status_by_id(cls, db: Session, status_id: int) -> WorkflowStatus | None:
        """
        根据ID查询工作流状态。
        :param db: 数据库会话
        :param status_id: 状态ID
        :return: 状态对象
        """
        return db.query(WorkflowStatus).filter(WorkflowStatus.id == status_id).first()

    @classmethod
    def get_workflow_status_by_code(cls, db: Session, code: str) -> WorkflowStatus | None:
        """
        根据编码查询工作流状态。
        :param db: 数据库会话
        :param code: 状态编码
        :return: 状态对象
        """
        return db.query(WorkflowStatus).filter(WorkflowStatus.code == code).first()

    @classmethod
    def add_workflow_status(cls, db: Session, status: WorkflowStatus) -> WorkflowStatus:
        """
        新增工作流状态。
        :param db: 数据库会话
        :param status: 状态对象
        :return: 状态对象
        """
        db.add(status)
        db.flush()
        return status

    @classmethod
    def update_workflow_status(cls, db: Session, status_id: int, data: dict) -> None:
        """
        更新工作流状态。
        :param db: 数据库会话
        :param status_id: 状态ID
        :param data: 更新字段
        :return: 无
        """
        db.query(WorkflowStatus).filter(WorkflowStatus.id == status_id).update(data)

    @classmethod
    def delete_workflow_status(cls, db: Session, status_id: int) -> None:
        """
        删除工作流状态。
        :param db: 数据库会话
        :param status_id: 状态ID
        :return: 无
        """
        db.query(WorkflowStatus).filter(WorkflowStatus.id == status_id).delete()

    @classmethod
    def list_workflow_transition(cls, db: Session) -> list[WorkflowTransition]:
        """
        查询工作流流转列表。
        :param db: 数据库会话
        :return: 流转列表
        """
        return db.query(WorkflowTransition).order_by(WorkflowTransition.create_time.asc()).all()

    @classmethod
    def get_workflow_transition_by_id(cls, db: Session, transition_id: int) -> WorkflowTransition | None:
        """
        根据ID查询工作流流转规则。
        :param db: 数据库会话
        :param transition_id: 流转ID
        :return: 流转规则对象
        """
        return db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).first()

    @classmethod
    def add_workflow_transition(cls, db: Session, transition: WorkflowTransition) -> WorkflowTransition:
        """
        新增工作流流转规则。
        :param db: 数据库会话
        :param transition: 流转规则对象
        :return: 流转规则对象
        """
        db.add(transition)
        db.flush()
        return transition

    @classmethod
    def update_workflow_transition(cls, db: Session, transition_id: int, data: dict) -> None:
        """
        更新工作流流转规则。
        :param db: 数据库会话
        :param transition_id: 流转ID
        :param data: 更新字段
        :return: 无
        """
        db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).update(data)

    @classmethod
    def delete_workflow_transition(cls, db: Session, transition_id: int) -> None:
        """
        删除工作流流转规则。
        :param db: 数据库会话
        :param transition_id: 流转ID
        :return: 无
        """
        db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).delete()

    @classmethod
    def count_status_usage(cls, db: Session, status_code: str) -> int:
        """
        统计状态编码在工单、状态历史和流转规则中的引用次数。
        :param db: 数据库会话
        :param status_code: 状态编码
        :return: 引用次数
        """
        ticket_count = db.query(func.count(Ticket.ticket_id)).filter(Ticket.status == status_code).scalar() or 0
        history_count = (
            db.query(func.count(TicketStatusHistory.id))
            .filter(
                or_(
                    TicketStatusHistory.from_status == status_code,
                    TicketStatusHistory.to_status == status_code,
                )
            )
            .scalar()
            or 0
        )
        transition_count = (
            db.query(func.count(WorkflowTransition.id))
            .filter(
                or_(
                    WorkflowTransition.from_status == status_code,
                    WorkflowTransition.to_status == status_code,
                )
            )
            .scalar()
            or 0
        )
        return ticket_count + history_count + transition_count

    @classmethod
    def upsert_rca(cls, db: Session, rca: TicketRca) -> TicketRca:
        """
        新增或更新工单 RCA。
        :param db: 数据库会话
        :param rca: RCA 对象
        :return: RCA 对象
        """
        existing = db.query(TicketRca).filter(TicketRca.ticket_id == rca.ticket_id).first()
        if not existing:
            db.add(rca)
            db.flush()
            return rca
        for column in TicketRca.__table__.columns:
            key = column.name
            if key in {"id", "ticket_id", "create_time"}:
                continue
            value = getattr(rca, key)
            if value is not None:
                setattr(existing, key, value)
        existing.update_time = datetime.now()
        db.flush()
        return existing

    @classmethod
    def add_knowledge(cls, db: Session, article: KnowledgeArticle) -> KnowledgeArticle:
        """
        新增知识库文章。
        :param db: 数据库会话
        :param article: 知识库文章对象
        :return: 文章对象
        """
        db.add(article)
        db.flush()
        return article

    @classmethod
    def get_knowledge(cls, db: Session, article_id: int) -> KnowledgeArticle | None:
        """
        根据文章ID获取知识库文章。
        :param db: 数据库会话
        :param article_id: 文章ID
        :return: 文章对象
        """
        return (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.article_id == article_id, KnowledgeArticle.del_flag == "0")
            .first()
        )

    @classmethod
    def update_knowledge(cls, db: Session, article_id: int, data: dict) -> None:
        """
        更新知识库文章。
        :param db: 数据库会话
        :param article_id: 文章ID
        :param data: 更新字段
        :return: 无
        """
        db.query(KnowledgeArticle).filter(KnowledgeArticle.article_id == article_id).update(data)

    @classmethod
    def get_knowledge_list(cls, db: Session, query: KnowledgeArticleQueryModel):
        """
        分页查询知识库文章。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        article_query = (
            db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.del_flag == "0",
                KnowledgeArticle.title.like(f"%{query.title}%") if query.title else True,
                KnowledgeArticle.category == query.category if query.category else True,
            )
            .filter(
                or_(
                    KnowledgeArticle.title.like(f"%{query.keyword}%"),
                    KnowledgeArticle.content.like(f"%{query.keyword}%"),
                )
                if query.keyword
                else True
            )
            .order_by(KnowledgeArticle.update_time.desc(), KnowledgeArticle.create_time.desc())
        )
        return PageUtil.paginate(article_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def get_ticket_statistics(
        cls,
        db: Session,
        begin_time: datetime | None,
        end_time: datetime | None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
    ) -> dict:
        """
        实时统计指定时间范围内的工单数量、分类和人员处理量。
        :param db: 数据库会话
        :param begin_time: 开始时间
        :param end_time: 结束时间
        :param project_ids: 项目ID多选过滤
        :param module_ids: 模块ID多选过滤
        :param module_codes: 模块业务码多选过滤
        :return: 统计结果
        """
        filters = [Ticket.del_flag == "0"]
        matched_module_ids_by_code = (
            _resolve_module_ids_by_codes(db, module_codes or [], project_ids or None)
            if module_codes
            else []
        )
        if begin_time:
            filters.append(Ticket.create_time >= begin_time)
        if end_time:
            filters.append(Ticket.create_time <= end_time)
        if project_ids:
            filters.append(Ticket.project_id.in_(project_ids))
        if module_ids:
            filters.append(Ticket.module_id.in_(module_ids))
        if module_codes:
            if matched_module_ids_by_code:
                filters.append(Ticket.module_id.in_(matched_module_ids_by_code))
            else:
                filters.append(Ticket.ticket_id == -1)

        base_filter = and_(*filters)
        total = db.query(func.count(Ticket.ticket_id)).filter(base_filter).scalar() or 0
        status_rows = (
            db.query(Ticket.status, func.count(Ticket.ticket_id)).filter(base_filter).group_by(Ticket.status).all()
        )
        category_rows = (
            db.query(Ticket.category_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.category_name)
            .all()
        )
        issue_type_rows = (
            db.query(Ticket.issue_type_id, Ticket.issue_type_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.issue_type_id, Ticket.issue_type_name)
            .all()
        )
        problem_rows = (
            db.query(Ticket.is_problem, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.is_problem)
            .all()
        )
        root_cause_type_rows = (
            db.query(Ticket.root_cause_type, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.root_cause_type)
            .all()
        )
        solution_type_rows = (
            db.query(Ticket.solution_type, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.solution_type)
            .all()
        )
        resolution_rows = (
            db.query(Ticket.resolution_code, Ticket.resolution_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.resolution_code, Ticket.resolution_name)
            .all()
        )
        module_rows = (
            db.query(Ticket.module_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.module_name)
            .all()
        )
        source_rows = (
            db.query(Ticket.source, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.source)
            .all()
        )
        priority_rows = (
            db.query(Ticket.internal_priority, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.internal_priority)
            .all()
        )
        assignee_rows = (
            db.query(Ticket.current_assignee_id, Ticket.current_assignee_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.current_assignee_id, Ticket.current_assignee_name)
            .all()
        )
        root_cause_rows = (
            db.query(TicketRca.root_cause_category, func.count(TicketRca.id))
            .join(Ticket, Ticket.ticket_id == TicketRca.ticket_id)
            .filter(base_filter)
            .group_by(TicketRca.root_cause_category)
            .all()
        )
        transition_filters = []
        if begin_time:
            transition_filters.append(TicketStatusHistory.create_time >= begin_time)
        if end_time:
            transition_filters.append(TicketStatusHistory.create_time <= end_time)
        if project_ids:
            transition_filters.append(Ticket.project_id.in_(project_ids))
        if module_ids:
            transition_filters.append(Ticket.module_id.in_(module_ids))
        if module_codes:
            if matched_module_ids_by_code:
                transition_filters.append(Ticket.module_id.in_(matched_module_ids_by_code))
            else:
                transition_filters.append(Ticket.ticket_id == -1)
        transition_rows = (
            db.query(
                TicketStatusHistory.from_status,
                TicketStatusHistory.to_status,
                func.count(TicketStatusHistory.id),
            )
            .join(Ticket, Ticket.ticket_id == TicketStatusHistory.ticket_id)
            .filter(Ticket.del_flag == "0", *transition_filters)
            .group_by(TicketStatusHistory.from_status, TicketStatusHistory.to_status)
            .all()
        )
        avg_process_seconds = (
            db.query(func.avg(Ticket.total_process_seconds))
            .filter(base_filter, Ticket.total_process_seconds > 0)
            .scalar()
            or 0
        )

        return {
            "total": total,
            "avg_process_seconds": int(avg_process_seconds),
            "status_counts": [{"status": row[0], "count": row[1]} for row in status_rows],
            "category_counts": [{"category": row[0] or "未分类", "count": row[1]} for row in category_rows],
            "issue_type_counts": [
                {
                    "issue_type_id": row[0] or "",
                    "issue_type_name": row[1] or row[0] or "未填写",
                    "count": row[2],
                }
                for row in issue_type_rows
            ],
            "problem_counts": [
                {
                    "is_problem": row[0],
                    "label": "真实问题" if row[0] is True else ("非问题" if row[0] is False else "未填写"),
                    "count": row[1],
                }
                for row in problem_rows
            ],
            "module_counts": [{"module": row[0] or "未填写", "count": row[1]} for row in module_rows],
            "source_counts": [{"source": row[0] or "未填写", "count": row[1]} for row in source_rows],
            "priority_counts": [{"priority": row[0] or "未填写", "count": row[1]} for row in priority_rows],
            "root_cause_counts": [{"root_cause": row[0] or "未填写", "count": row[1]} for row in root_cause_rows],
            "root_cause_type_counts": [
                {"root_cause_type": row[0] or "未填写", "count": row[1]} for row in root_cause_type_rows
            ],
            "solution_type_counts": [
                {"solution_type": row[0] or "未填写", "count": row[1]} for row in solution_type_rows
            ],
            "resolution_counts": [
                {
                    "resolution_code": row[0] or "",
                    "resolution_name": row[1] or row[0] or "未填写",
                    "count": row[2],
                }
                for row in resolution_rows
            ],
            "transition_counts": [
                {"from_status": row[0] or "创建", "to_status": row[1], "count": row[2]} for row in transition_rows
            ],
            "assignee_counts": [
                {"user_id": row[0], "user_name": row[1] or "未指派", "count": row[2]} for row in assignee_rows
            ],
        }

    @classmethod
    def upsert_embedding_record(cls, db: Session, record: EmbeddingRecord) -> EmbeddingRecord:
        """
        新增或更新对象向量记录。
        :param db: 数据库会话
        :param record: 向量记录对象
        :return: 保存后的向量记录
        """
        existing = (
            db.query(EmbeddingRecord)
            .filter(
                EmbeddingRecord.object_type == record.object_type,
                EmbeddingRecord.object_id == record.object_id,
                EmbeddingRecord.embedding_model == record.embedding_model,
                EmbeddingRecord.embedding_version == record.embedding_version,
            )
            .first()
        )
        if existing:
            existing.embedding_dimension = record.embedding_dimension
            existing.embedding = record.embedding
            existing.content_hash = record.content_hash
            existing.create_time = datetime.now()
            db.flush()
            return existing
        db.add(record)
        db.flush()
        return record

    @classmethod
    def list_ticket_embedding_records(
        cls, db: Session, model: str = "local-hash", version: str = "v1"
    ) -> list[EmbeddingRecord]:
        """
        查询工单向量记录。
        :param db: 数据库会话
        :param model: 向量模型标识
        :param version: 向量版本
        :return: 向量记录列表
        """
        return (
            db.query(EmbeddingRecord)
            .filter(
                EmbeddingRecord.object_type == "ticket",
                EmbeddingRecord.embedding_model == model,
                EmbeddingRecord.embedding_version == version,
            )
            .all()
        )

    @classmethod
    def list_tickets_for_embedding(
        cls, db: Session, *, offset: int = 0, limit: int = 100, ticket_ids: list[int] | None = None
    ) -> list[Ticket]:
        """
        分页查询需要重建向量的有效工单。
        :param db: 数据库会话
        :param offset: 分页偏移量
        :param limit: 返回数量
        :param ticket_ids: 可选的指定工单ID列表
        :return: 工单列表
        """
        query = db.query(Ticket).filter(Ticket.del_flag == "0")
        if ticket_ids:
            query = query.filter(Ticket.ticket_id.in_(ticket_ids))
        return query.order_by(Ticket.update_time.desc(), Ticket.create_time.desc()).offset(offset).limit(limit).all()

    @classmethod
    def count_tickets_for_embedding(cls, db: Session, ticket_ids: list[int] | None = None) -> int:
        """
        统计需要重建向量的有效工单数量。
        :param db: 数据库会话
        :param ticket_ids: 可选的指定工单ID列表
        :return: 工单数量
        """
        query = db.query(func.count(Ticket.ticket_id)).filter(Ticket.del_flag == "0")
        if ticket_ids:
            query = query.filter(Ticket.ticket_id.in_(ticket_ids))
        return int(query.scalar() or 0)

    @classmethod
    def list_rca_by_ticket_ids(cls, db: Session, ticket_ids: list[int]) -> dict[int, TicketRca]:
        """
        批量查询工单 RCA 并按工单ID映射。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 工单ID到 RCA 的映射
        """
        if not ticket_ids:
            return {}
        rows = db.query(TicketRca).filter(TicketRca.ticket_id.in_(ticket_ids)).all()
        return {row.ticket_id: row for row in rows}

    @classmethod
    def search_tickets_by_keyword(cls, db: Session, keyword: str, limit: int = 20) -> list[Ticket]:
        """
        按自然语言关键字匹配工单文本字段。
        :param db: 数据库会话
        :param keyword: 搜索文本
        :param limit: 返回数量
        :return: 工单列表
        """
        if not keyword:
            return []
        return (
            db.query(Ticket)
            .filter(Ticket.del_flag == "0")
            .filter(
                or_(
                    Ticket.ticket_no.like(f"%{keyword}%"),
                    Ticket.title.like(f"%{keyword}%"),
                    Ticket.description.like(f"%{keyword}%"),
                    Ticket.module_name.like(f"%{keyword}%"),
                    Ticket.category_name.like(f"%{keyword}%"),
                    Ticket.root_cause.like(f"%{keyword}%"),
                    Ticket.solution.like(f"%{keyword}%"),
                )
            )
            .order_by(Ticket.update_time.desc(), Ticket.create_time.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_user_options(cls, db: Session, keyword: str | None = None, limit: int = 20) -> list[SysUser]:
        """
        查询可用于工单指派的用户选项。
        :param db: 数据库会话
        :param keyword: 用户名、昵称或手机号关键字
        :param limit: 返回数量限制
        :return: 用户列表
        """
        query = db.query(SysUser).filter(SysUser.del_flag == "0", SysUser.status == "0")
        if keyword:
            query = query.filter(
                or_(
                    SysUser.user_name.like(f"%{keyword}%"),
                    SysUser.nick_name.like(f"%{keyword}%"),
                    SysUser.phonenumber.like(f"%{keyword}%"),
                )
            )
        return query.order_by(SysUser.user_id.asc()).limit(limit).all()

    @classmethod
    def get_user_by_id(cls, db: Session, user_id: int | None) -> SysUser | None:
        """
        根据用户ID查询有效用户。
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户对象
        """
        if not user_id:
            return None
        return (
            db.query(SysUser)
            .filter(SysUser.user_id == user_id, SysUser.del_flag == "0", SysUser.status == "0")
            .first()
        )
