"""可配置趋势指标快照的数据访问层。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.entity.do.ticket_do import TicketStatisticsMetricSnapshot


class TicketStatisticsMetricSnapshotDao:
    """只负责通用指标快照的覆盖写入和范围读取。"""

    @classmethod
    def replace_snapshot_rows(cls, db: Session, snapshot_type: str, snapshot_key: str, rows: list[dict[str, Any]]) -> None:
        """按快照类型和时间键删除旧结果后写入本次完整计算结果。"""
        db.query(TicketStatisticsMetricSnapshot).filter(
            TicketStatisticsMetricSnapshot.snapshot_type == snapshot_type,
            TicketStatisticsMetricSnapshot.snapshot_key == snapshot_key,
        ).delete(synchronize_session=False)
        now = datetime.now()
        for item in rows:
            db.add(TicketStatisticsMetricSnapshot(**item, snapshot_type=snapshot_type, snapshot_key=snapshot_key, create_time=now, update_time=now))

    @classmethod
    def list_between(
        cls, db: Session, snapshot_type: str, begin_key: str | None, end_key: str | None,
        metric_codes: list[str] | None = None, project_ids: list[int] | None = None,
        module_ids: list[int] | None = None, issue_type_ids: list[str] | None = None, snapshot_scope: str = "all",
    ) -> list[TicketStatisticsMetricSnapshot]:
        """读取指定范围、维度和指标的快照行。"""
        query = db.query(TicketStatisticsMetricSnapshot).filter(
            TicketStatisticsMetricSnapshot.snapshot_type == snapshot_type,
            TicketStatisticsMetricSnapshot.snapshot_scope == snapshot_scope,
        )
        if begin_key:
            query = query.filter(TicketStatisticsMetricSnapshot.snapshot_key >= begin_key)
        if end_key:
            query = query.filter(TicketStatisticsMetricSnapshot.snapshot_key <= end_key)
        if metric_codes:
            query = query.filter(TicketStatisticsMetricSnapshot.metric_code.in_(metric_codes))
        if project_ids:
            query = query.filter(TicketStatisticsMetricSnapshot.project_id.in_(project_ids))
        if module_ids:
            query = query.filter(TicketStatisticsMetricSnapshot.module_id.in_(module_ids))
        if issue_type_ids:
            query = query.filter(TicketStatisticsMetricSnapshot.issue_type_id.in_(issue_type_ids))
        return query.order_by(TicketStatisticsMetricSnapshot.snapshot_key.asc(), TicketStatisticsMetricSnapshot.metric_code.asc()).all()
