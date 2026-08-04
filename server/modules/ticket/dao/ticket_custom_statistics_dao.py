"""工单自定义统计的数据访问层。"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_processing_stats_dao import TicketProcessingStatsDao
from modules.ticket.entity.do.ticket_do import Ticket


class TicketCustomStatisticsDao:
    """按单一白名单时间字段查询实时工单统计范围。"""

    TIME_COLUMN_REGISTRY = {
        "submitTime": Ticket.submit_time,
        "createTime": Ticket.create_time,
        "firstResponseAt": Ticket.first_response_at,
        "processedAt": Ticket.processed_at,
        "resolvedAt": Ticket.resolved_at,
        "closedAt": Ticket.closed_at,
    }

    @classmethod
    def list_tickets(
        cls,
        db: Session,
        *,
        time_field: str,
        start_time: datetime,
        end_time: datetime,
        scope: dict[str, Any],
    ) -> Iterable[Ticket]:
        """按配置范围流式返回工单 ORM 实体，时间区间为左闭右开。"""
        time_column = cls.TIME_COLUMN_REGISTRY[time_field]
        filters = TicketProcessingStatsDao.build_scope_filters(
            db,
            project_ids=scope.get("projectIds"),
            module_ids=scope.get("moduleIds"),
            module_codes=scope.get("moduleCodes"),
            issue_type_ids=scope.get("issueTypeIds"),
            problem_pattern_codes=scope.get("problemPatternCodes"),
        )
        return (
            db.query(Ticket)
            .filter(*filters, time_column >= start_time, time_column < end_time)
            .order_by(time_column.desc(), Ticket.ticket_id.desc())
            .yield_per(500)
        )
