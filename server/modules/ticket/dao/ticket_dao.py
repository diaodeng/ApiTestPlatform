from datetime import date, datetime, time

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from module_admin.entity.do.user_do import SysUser
from modules.ticket.entity.do.ticket_do import (
    KnowledgeArticle,
    Ticket,
    TicketAssignHistory,
    TicketComment,
    TicketEvent,
    TicketRca,
    TicketStatusHistory,
    WorkflowStatus,
    WorkflowTransition,
)
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
    def get_ticket_list(cls, db: Session, query: TicketQueryModel):
        """
        根据查询条件分页获取工单列表。
        :param db: 数据库会话
        :param query: 工单查询参数
        :return: 分页结果或列表
        """
        begin_time = _date_start(query.begin_time)
        end_time = _date_end(query.end_time)
        ticket_query = (
            db.query(Ticket)
            .filter(
                Ticket.del_flag == "0",
                Ticket.ticket_no.like(f"%{query.ticket_no}%") if query.ticket_no else True,
                Ticket.title.like(f"%{query.title}%") if query.title else True,
                Ticket.status == query.status if query.status else True,
                Ticket.project_id == query.project_id if query.project_id else True,
                Ticket.merchant_name.like(f"%{query.merchant_name}%") if query.merchant_name else True,
                Ticket.module_id == query.module_id if query.module_id else True,
                Ticket.module_name.like(f"%{query.module_name}%") if query.module_name else True,
                Ticket.category_id == query.category_id if query.category_id else True,
                Ticket.customer_priority == query.customer_priority if query.customer_priority else True,
                Ticket.internal_priority == query.internal_priority if query.internal_priority else True,
                Ticket.source == query.source if query.source else True,
                Ticket.current_assignee_id == query.current_assignee_id if query.current_assignee_id else True,
                Ticket.reporter_id == query.reporter_id if query.reporter_id else True,
                Ticket.create_time >= begin_time if begin_time else True,
                Ticket.create_time <= end_time if end_time else True,
            )
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
        db.add(comment)
        db.flush()
        return comment

    @classmethod
    def add_event(cls, db: Session, event: TicketEvent) -> TicketEvent:
        """
        新增工单事件。
        :param db: 数据库会话
        :param event: 事件对象
        :return: 事件对象
        """
        db.add(event)
        db.flush()
        return event

    @classmethod
    def get_timeline(cls, db: Session, ticket_id: int) -> dict:
        """
        获取工单时间线相关数据。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 状态历史、指派历史、评论、事件和 RCA
        """
        return {
            "status_history": db.query(TicketStatusHistory)
            .filter(TicketStatusHistory.ticket_id == ticket_id)
            .order_by(TicketStatusHistory.started_at.asc())
            .all(),
            "assign_history": db.query(TicketAssignHistory)
            .filter(TicketAssignHistory.ticket_id == ticket_id)
            .order_by(TicketAssignHistory.assigned_at.asc())
            .all(),
            "comments": db.query(TicketComment)
            .filter(TicketComment.ticket_id == ticket_id)
            .order_by(TicketComment.create_time.asc())
            .all(),
            "events": db.query(TicketEvent)
            .filter(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.create_time.asc())
            .all(),
            "rca": db.query(TicketRca).filter(TicketRca.ticket_id == ticket_id).first(),
        }

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
    def get_ticket_statistics(cls, db: Session, begin_time: datetime | None, end_time: datetime | None) -> dict:
        """
        实时统计指定时间范围内的工单数量、分类和人员处理量。
        :param db: 数据库会话
        :param begin_time: 开始时间
        :param end_time: 结束时间
        :return: 统计结果
        """
        filters = [Ticket.del_flag == "0"]
        if begin_time:
            filters.append(Ticket.create_time >= begin_time)
        if end_time:
            filters.append(Ticket.create_time <= end_time)

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
        assignee_rows = (
            db.query(Ticket.current_assignee_id, Ticket.current_assignee_name, func.count(Ticket.ticket_id))
            .filter(base_filter)
            .group_by(Ticket.current_assignee_id, Ticket.current_assignee_name)
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
            "assignee_counts": [
                {"user_id": row[0], "user_name": row[1] or "未指派", "count": row[2]} for row in assignee_rows
            ],
        }

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
