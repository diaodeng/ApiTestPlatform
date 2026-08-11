from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import Ticket, TicketIssue, TicketRelation
from modules.ticket.entity.vo.ticket_issue_vo import TicketIssueQueryModel
from utils.page_util import PageUtil


class TicketIssueDao:
    """
    问题实例归因 DAO，只封装 Issue、Ticket 归属和补充关系的查询与持久化。
    """

    @classmethod
    def get_issue_by_id(cls, db: Session, issue_id: int | None) -> TicketIssue | None:
        """
        根据问题实例ID查询有效 Issue。
        :param db: 数据库会话
        :param issue_id: 问题实例ID
        :return: 问题实例
        """
        if not issue_id:
            return None
        return db.query(TicketIssue).filter(TicketIssue.issue_id == issue_id, TicketIssue.del_flag == "0").first()

    @classmethod
    def get_issue_by_no(cls, db: Session, issue_no: str) -> TicketIssue | None:
        """
        根据问题实例编号查询有效 Issue。
        :param db: 数据库会话
        :param issue_no: 问题实例编号
        :return: 问题实例
        """
        normalized_no = str(issue_no or "").strip()
        if not normalized_no:
            return None
        return db.query(TicketIssue).filter(TicketIssue.issue_no == normalized_no, TicketIssue.del_flag == "0").first()

    @classmethod
    def get_issue_list(cls, db: Session, query: TicketIssueQueryModel):
        """
        分页查询问题实例。
        :param db: 数据库会话
        :param query: 查询条件
        :return: 分页对象或列表
        """
        issue_no = str(query.issue_no or "").strip()
        title = str(query.title or "").strip()
        keyword = str(query.keyword or "").strip()
        issue_query = (
            db.query(TicketIssue)
            .filter(
                TicketIssue.del_flag == "0",
                TicketIssue.issue_no.like(f"%{issue_no}%") if issue_no else True,
                TicketIssue.title.like(f"%{title}%") if title else True,
                TicketIssue.status == query.status if query.status else True,
                TicketIssue.project_id == query.project_id if query.project_id else True,
                TicketIssue.module_id == query.module_id if query.module_id else True,
                TicketIssue.owner_id == query.owner_id if query.owner_id else True,
                TicketIssue.problem_pattern_code == query.problem_pattern_code
                if query.problem_pattern_code
                else True,
            )
            .filter(
                or_(
                    TicketIssue.issue_no.like(f"%{keyword}%"),
                    TicketIssue.title.like(f"%{keyword}%"),
                    TicketIssue.summary.like(f"%{keyword}%"),
                )
                if keyword
                else True
            )
            .order_by(TicketIssue.update_time.desc(), TicketIssue.issue_id.desc())
        )
        return PageUtil.paginate(issue_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def add_issue(cls, db: Session, issue: TicketIssue) -> TicketIssue:
        """
        新增问题实例。
        :param db: 数据库会话
        :param issue: 问题实例实体
        :return: 保存后的实体
        """
        db.add(issue)
        db.flush()
        return issue

    @classmethod
    def update_issue(cls, db: Session, issue_id: int, data: dict[str, Any]) -> None:
        """
        更新问题实例字段。
        :param db: 数据库会话
        :param issue_id: 问题实例ID
        :param data: 待更新字段
        :return: 无
        """
        db.query(TicketIssue).filter(TicketIssue.issue_id == issue_id).update(data)
        db.flush()

    @classmethod
    def get_ticket_by_id(cls, db: Session, ticket_id: int | None) -> Ticket | None:
        """
        根据工单ID查询有效工单。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 工单实体
        """
        if not ticket_id:
            return None
        return db.query(Ticket).filter(Ticket.ticket_id == ticket_id, Ticket.del_flag == "0").first()

    @classmethod
    def list_tickets_by_issue_id(cls, db: Session, issue_id: int | None) -> list[Ticket]:
        """
        查询归属到指定问题实例的有效工单。
        :param db: 数据库会话
        :param issue_id: 问题实例ID
        :return: 工单列表
        """
        if not issue_id:
            return []
        return (
            db.query(Ticket)
            .filter(Ticket.issue_id == issue_id, Ticket.del_flag == "0")
            .order_by(Ticket.create_time.asc(), Ticket.ticket_id.asc())
            .all()
        )

    @classmethod
    def count_tickets_by_issue_id(cls, db: Session, issue_id: int | None) -> int:
        """
        统计指定 Issue 下有效工单数量，软删除工单不计入。
        :param db: 数据库会话
        :param issue_id: 问题实例ID
        :return: 工单数
        """
        if not issue_id:
            return 0
        return int(
            db.query(func.count(Ticket.ticket_id))
            .filter(Ticket.issue_id == issue_id, Ticket.del_flag == "0")
            .scalar()
            or 0
        )

    @classmethod
    def update_ticket_issue(
        cls,
        db: Session,
        ticket_id: int,
        issue_id: int | None,
        relation_type: str | None,
        confirmed: bool,
        update_by: str,
    ) -> None:
        """
        更新工单主归因字段。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param issue_id: 归属 Issue ID，None 表示解绑
        :param relation_type: 归属类型
        :param confirmed: 是否确认
        :param update_by: 更新人
        :return: 无
        """
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).update(
            {
                "issue_id": issue_id,
                "issue_relation_type": relation_type or "",
                "issue_confirmed": bool(confirmed),
                "update_by": update_by,
                "update_time": datetime.now(),
            }
        )
        db.flush()

    @classmethod
    def list_issue_summary_by_ids(cls, db: Session, issue_ids: list[int]) -> dict[int, TicketIssue]:
        """
        批量查询 Issue 摘要并按 ID 映射。
        :param db: 数据库会话
        :param issue_ids: Issue ID 列表
        :return: Issue ID 到实体的映射
        """
        normalized_ids = [int(item) for item in issue_ids if item]
        if not normalized_ids:
            return {}
        rows = db.query(TicketIssue).filter(TicketIssue.del_flag == "0", TicketIssue.issue_id.in_(normalized_ids)).all()
        return {row.issue_id: row for row in rows}

    @classmethod
    def get_relation(
        cls,
        db: Session,
        source_ticket_id: int,
        target_ticket_id: int,
        relation_type: str,
    ) -> TicketRelation | None:
        """
        查询未删除的工单补充关系。
        :param db: 数据库会话
        :param source_ticket_id: 源工单ID
        :param target_ticket_id: 目标工单ID
        :param relation_type: 关系类型
        :return: 工单关系
        """
        return (
            db.query(TicketRelation)
            .filter(
                TicketRelation.source_ticket_id == source_ticket_id,
                TicketRelation.target_ticket_id == target_ticket_id,
                TicketRelation.relation_type == relation_type,
                TicketRelation.del_flag == "0",
            )
            .first()
        )

    @classmethod
    def get_relation_by_id(cls, db: Session, relation_id: int | None) -> TicketRelation | None:
        """
        根据关系ID查询未删除补充关系。
        :param db: 数据库会话
        :param relation_id: 关系ID
        :return: 工单关系
        """
        if not relation_id:
            return None
        return (
            db.query(TicketRelation)
            .filter(TicketRelation.relation_id == relation_id, TicketRelation.del_flag == "0")
            .first()
        )

    @classmethod
    def add_relation(cls, db: Session, relation: TicketRelation) -> TicketRelation:
        """
        新增工单补充关系。
        :param db: 数据库会话
        :param relation: 关系实体
        :return: 保存后的实体
        """
        db.add(relation)
        db.flush()
        return relation

    @classmethod
    def update_relation(cls, db: Session, relation_id: int, data: dict[str, Any]) -> None:
        """
        更新工单补充关系。
        :param db: 数据库会话
        :param relation_id: 关系ID
        :param data: 待更新字段
        :return: 无
        """
        db.query(TicketRelation).filter(TicketRelation.relation_id == relation_id).update(data)
        db.flush()

    @classmethod
    def list_relations_by_ticket_ids(cls, db: Session, ticket_ids: list[int]) -> list[TicketRelation]:
        """
        查询工单集合相关的补充关系。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 关系列表
        """
        normalized_ids = [int(item) for item in ticket_ids if item]
        if not normalized_ids:
            return []
        return (
            db.query(TicketRelation)
            .filter(
                TicketRelation.del_flag == "0",
                and_(
                    TicketRelation.source_ticket_id.in_(normalized_ids),
                    TicketRelation.target_ticket_id.in_(normalized_ids),
                ),
            )
            .order_by(TicketRelation.create_time.desc(), TicketRelation.relation_id.desc())
            .all()
        )

    @classmethod
    def list_issue_related_relations(cls, db: Session, issue_id: int | None) -> list[TicketRelation]:
        """
        查询某个 Issue 下所有绑定工单之间的补充关系。
        :param db: 数据库会话
        :param issue_id: 问题实例ID
        :return: 关系列表
        """
        if not issue_id:
            return []
        ticket_ids = [row.ticket_id for row in cls.list_tickets_by_issue_id(db, issue_id) if row.ticket_id]
        if not ticket_ids:
            return []
        return cls.list_relations_by_ticket_ids(db, ticket_ids)
