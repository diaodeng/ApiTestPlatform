from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import (
    _resolve_module_ids_by_codes,
    _resolve_ticket_submit_time,
    _ticket_submit_time_expr,
)
from modules.ticket.entity.do.ticket_do import Ticket


class TicketProcessingStatsDao:
    """
    工单处理统计数据访问层。

    仅封装统计所需的工单范围查询，不在 DAO 中计算处理率、耗时等业务指标。
    """

    @classmethod
    def build_scope_filters(
        cls,
        db: Session,
        *,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
        problem_pattern_codes: list[str] | None = None,
    ) -> list[Any]:
        """
        构造统计共用的项目、模块和细分问题过滤条件。
        :param db: 数据库会话。
        :param project_ids: 项目ID列表。
        :param module_ids: 模块ID列表。
        :param module_codes: 模块业务码列表。
        :param issue_type_ids: 工单类型编码列表。
        :param problem_pattern_codes: 细分问题编码列表。
        :return: SQLAlchemy 过滤条件列表。
        """
        filters: list[Any] = [Ticket.del_flag == "0"]
        if project_ids:
            filters.append(Ticket.project_id.in_(project_ids))
        if module_ids:
            filters.append(Ticket.module_id.in_(module_ids))
        if module_codes:
            matched_module_ids = _resolve_module_ids_by_codes(db, module_codes, project_ids or None)
            filters.append(Ticket.module_id.in_(matched_module_ids) if matched_module_ids else Ticket.ticket_id == -1)
        if issue_type_ids:
            filters.append(Ticket.issue_type_id.in_(issue_type_ids))
        if problem_pattern_codes:
            filters.append(Ticket.problem_pattern_code.in_(problem_pattern_codes))
        return filters

    @classmethod
    def list_metric_tickets(
        cls,
        db: Session,
        *,
        begin_time: datetime | None,
        end_time: datetime | None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
        problem_pattern_codes: list[str] | None = None,
    ) -> Iterable[Any]:
        """
        查询处理统计需要扫描的工单集合。
        :param db: 数据库会话。
        :param begin_time: 统计开始时间。
        :param end_time: 统计结束时间。
        :param project_ids: 项目ID列表。
        :param module_ids: 模块ID列表。
        :param module_codes: 模块业务码列表。
        :param issue_type_ids: 工单类型编码列表。
        :param problem_pattern_codes: 细分问题编码列表。
        :return: 轻量字段行迭代器。
        """
        submit_time_expr = _ticket_submit_time_expr()
        filters = cls.build_scope_filters(
            db,
            project_ids=project_ids,
            module_ids=module_ids,
            module_codes=module_codes,
            issue_type_ids=issue_type_ids,
            problem_pattern_codes=problem_pattern_codes,
        )
        if begin_time or end_time:
            time_filters = []
            for column in (
                submit_time_expr,
                Ticket.first_response_at,
                Ticket.processed_at,
                Ticket.resolved_at,
                Ticket.closed_at,
            ):
                column_filters = []
                if begin_time:
                    column_filters.append(column >= begin_time)
                if end_time:
                    column_filters.append(column <= end_time)
                time_filters.append(and_(*column_filters))
            filters.append(or_(*time_filters))
        query = (
            db.query(
                Ticket.ticket_id.label("ticket_id"),
                submit_time_expr.label("submit_time"),
                Ticket.create_time.label("create_time"),
                Ticket.first_response_at.label("first_response_at"),
                Ticket.processed_at.label("processed_at"),
                Ticket.resolved_at.label("resolved_at"),
                Ticket.closed_at.label("closed_at"),
            )
            .filter(and_(*filters))
            .order_by(submit_time_expr.asc(), Ticket.ticket_id.asc())
        )
        return query.yield_per(1000)

    @classmethod
    def list_trend_tickets(
        cls,
        db: Session,
        *,
        end_time: datetime | None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
        problem_pattern_codes: list[str] | None = None,
    ) -> list[Any]:
        """
        查询趋势统计所需的工单集合，保留周期前已提交的工单用于存量计算。
        :param db: 数据库会话。
        :param end_time: 趋势结束时间。
        :param project_ids: 项目ID列表。
        :param module_ids: 模块ID列表。
        :param module_codes: 模块业务码列表。
        :param issue_type_ids: 工单类型编码列表。
        :param problem_pattern_codes: 细分问题编码列表。
        :return: 轻量字段行列表。
        """
        submit_time_expr = _ticket_submit_time_expr()
        filters = cls.build_scope_filters(
            db,
            project_ids=project_ids,
            module_ids=module_ids,
            module_codes=module_codes,
            issue_type_ids=issue_type_ids,
            problem_pattern_codes=problem_pattern_codes,
        )
        if end_time:
            filters.append(submit_time_expr <= end_time)
        query = (
            db.query(
                Ticket.ticket_id.label("ticket_id"),
                submit_time_expr.label("submit_time"),
                Ticket.create_time.label("create_time"),
                Ticket.first_response_at.label("first_response_at"),
                Ticket.processed_at.label("processed_at"),
                Ticket.resolved_at.label("resolved_at"),
                Ticket.closed_at.label("closed_at"),
            )
            .filter(and_(*filters))
            .order_by(submit_time_expr.asc(), Ticket.ticket_id.asc())
        )
        return list(query.yield_per(1000))

    @classmethod
    def resolve_submit_time(cls, ticket: Ticket) -> datetime | None:
        """
        解析单条工单业务提交时间。
        :param ticket: 工单实体。
        :return: 提交时间。
        """
        return _resolve_ticket_submit_time(ticket)
