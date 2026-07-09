from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import TicketStatisticsDaily


class TicketStatisticsDailyDao:
    """
    工单每日快照数据访问层。
    """

    @classmethod
    def get_by_date(cls, db: Session, statistics_date: date) -> TicketStatisticsDaily | None:
        """
        按日期获取每日快照。
        :param db: 数据库会话。
        :param statistics_date: 统计日期。
        :return: 每日快照记录。
        """
        return (
            db.query(TicketStatisticsDaily)
            .filter(TicketStatisticsDaily.statistics_date == statistics_date)
            .one_or_none()
        )

    @classmethod
    def upsert_by_date(cls, db: Session, statistics_date: date, payload: dict[str, Any]) -> TicketStatisticsDaily:
        """
        按日期写入或更新每日快照。
        :param db: 数据库会话。
        :param statistics_date: 统计日期。
        :param payload: 聚合结果。
        :return: 写入后的快照记录。
        """
        row = cls.get_by_date(db, statistics_date)
        if row is None:
            row = TicketStatisticsDaily(statistics_date=statistics_date, create_time=datetime.now())
            db.add(row)
        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)
        db.flush()
        return row

    @classmethod
    def list_between(cls, db: Session, begin_date: date | None, end_date: date | None) -> list[TicketStatisticsDaily]:
        """
        查询日期范围内的每日快照。
        :param db: 数据库会话。
        :param begin_date: 开始日期。
        :param end_date: 结束日期。
        :return: 快照列表。
        """
        query = db.query(TicketStatisticsDaily)
        if begin_date is not None:
            query = query.filter(TicketStatisticsDaily.statistics_date >= begin_date)
        if end_date is not None:
            query = query.filter(TicketStatisticsDaily.statistics_date <= end_date)
        return query.order_by(TicketStatisticsDaily.statistics_date.asc()).all()
