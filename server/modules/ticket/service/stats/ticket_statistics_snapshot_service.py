from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import _date_end
from modules.ticket.dao.ticket_processing_stats_dao import TicketProcessingStatsDao
from modules.ticket.dao.ticket_statistics_daily_dao import TicketStatisticsDailyDao
from modules.ticket.entity.do.ticket_do import Ticket
from utils.log_util import logger


class TicketStatisticsSnapshotService:
    """
    工单每日快照服务。
    """

    @classmethod
    def build_daily_snapshot(cls, db: Session, statistics_date: date | None = None) -> dict[str, Any]:
        """
        生成并落库某一天的工单快照。
        :param db: 数据库会话。
        :param statistics_date: 统计日期，默认今天。
        :return: 写入摘要。
        """
        target_date = statistics_date or date.today()
        end_time = _date_end(target_date)
        begin_time = datetime.combine(target_date, time.min)
        rows = TicketProcessingStatsDao.list_trend_tickets(
            db,
            end_time=end_time,
            project_ids=None,
            module_ids=None,
            module_codes=None,
        )
        total_count = db.query(Ticket.ticket_id).filter(Ticket.del_flag == "0").count()
        submitted_rows = [
            ticket
            for ticket in rows
            if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), begin_time, end_time)
        ]
        first_responded_rows = [
            ticket for ticket in rows if cls._in_range(ticket.first_response_at, begin_time, end_time)
        ]
        processed_rows = [ticket for ticket in rows if cls._in_range(ticket.processed_at, begin_time, end_time)]
        resolved_rows = [ticket for ticket in rows if cls._in_range(ticket.resolved_at, begin_time, end_time)]
        closed_rows = [ticket for ticket in rows if cls._in_range(ticket.closed_at, begin_time, end_time)]
        processed_in_new_rows = [
            ticket
            for ticket in submitted_rows
            if isinstance(ticket.processed_at, datetime) and ticket.processed_at <= end_time
        ]
        unprocessed_backlog = sum(
            1
            for ticket in rows
            if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), None, end_time)
            and (not isinstance(ticket.processed_at, datetime) or ticket.processed_at > end_time)
        )
        open_backlog = sum(
            1
            for ticket in rows
            if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), None, end_time)
            and (not isinstance(ticket.closed_at, datetime) or ticket.closed_at > end_time)
        )
        payload = {
            "total_count": total_count,
            "submitted_count": len(submitted_rows),
            "first_responded_count": len(first_responded_rows),
            "processed_count": len(processed_rows),
            "processed_in_new_count": len(processed_in_new_rows),
            "process_rate": round(len(processed_in_new_rows) / len(submitted_rows), 4) if submitted_rows else 0,
            "resolved_count": len(resolved_rows),
            "closed_count": len(closed_rows),
            "unprocessed_backlog": unprocessed_backlog,
            "open_backlog": open_backlog,
            "avg_first_response_seconds": cls._average_seconds(first_responded_rows, "first_response_at"),
            "avg_first_process_seconds": cls._average_seconds(processed_rows, "processed_at"),
            "avg_resolve_seconds": cls._average_seconds(resolved_rows, "resolved_at"),
            "avg_close_seconds": cls._average_seconds(closed_rows, "closed_at"),
        }
        TicketStatisticsDailyDao.upsert_by_date(db, target_date, payload)
        db.commit()
        logger.info(f"工单每日快照已生成 | statistics_date={target_date}, submitted_count={len(submitted_rows)}")
        return {"statisticsDate": target_date.isoformat(), **payload}

    @staticmethod
    def _in_range(value: datetime | None, begin_time: datetime | None, end_time: datetime | None) -> bool:
        """
        判断时间是否在给定范围内。
        :param value: 待判断时间。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :return: 是否命中范围。
        """
        if not isinstance(value, datetime):
            return False
        if begin_time is not None and value < begin_time:
            return False
        if end_time is not None and value > end_time:
            return False
        return True

    @staticmethod
    def _average_seconds(rows: list[Ticket], field_name: str) -> int:
        """
        计算指定字段的平均耗时秒数。
        :param rows: 工单列表。
        :param field_name: 时间字段名。
        :return: 平均秒数。
        """
        values: list[int] = []
        for ticket in rows:
            value = getattr(ticket, field_name, None)
            submit_time = TicketProcessingStatsDao.resolve_submit_time(ticket)
            if not isinstance(value, datetime) or not isinstance(submit_time, datetime):
                continue
            seconds = int((value - submit_time).total_seconds())
            if seconds >= 0:
                values.append(seconds)
        return int(sum(values) / len(values)) if values else 0
