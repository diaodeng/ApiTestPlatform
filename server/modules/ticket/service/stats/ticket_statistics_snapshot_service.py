from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import _date_end
from modules.ticket.dao.ticket_processing_stats_dao import TicketProcessingStatsDao
from modules.ticket.dao.ticket_statistics_daily_dao import TicketStatisticsDailyDao
from modules.ticket.dao.ticket_statistics_period_snapshot_dao import TicketStatisticsPeriodSnapshotDao
from modules.ticket.dao.ticket_statistics_metric_snapshot_dao import TicketStatisticsMetricSnapshotDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.stats.ticket_custom_metric_service import TicketCustomMetricService
from modules.ticket.util.ticket_statistics_time_util import TicketStatisticsTimeUtil
from utils.log_util import logger


class TicketStatisticsSnapshotService:
    """
    工单每日快照服务。
    """

    SCOPE_ALL = "all"
    SCOPE_LEAF = "leaf"
    PERIOD_TYPE_BUSINESS_WEEK = "business_week"

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
        module_code_map = TicketStatisticsDailyDao.build_module_code_map(
            db,
            [int(ticket.module_id) for ticket in rows if getattr(ticket, "module_id", None)],
        )
        project_name_map = TicketStatisticsDailyDao.build_project_name_map(
            db,
            [int(ticket.project_id) for ticket in rows if getattr(ticket, "project_id", None)],
        )
        all_payload = cls.build_metric_payload(rows, begin_time, end_time)
        TicketStatisticsDailyDao.upsert_by_scope(
            db,
            target_date,
            {
                **all_payload,
                "snapshot_scope": cls.SCOPE_ALL,
                "project_id": 0,
                "project_name": "",
                "module_id": 0,
                "module_name": "",
                "module_code": "",
                "issue_type_id": "",
                "issue_type_name": "",
            },
            snapshot_scope=cls.SCOPE_ALL,
        )
        leaf_count = 0
        for dimension_rows in cls.group_leaf_rows(rows).values():
            sample = dimension_rows[0]
            project_id = int(getattr(sample, "project_id", None) or 0)
            module_id = int(getattr(sample, "module_id", None) or 0)
            issue_type_id = str(getattr(sample, "issue_type_id", None) or "").strip()
            payload = cls.build_metric_payload(dimension_rows, begin_time, end_time)
            TicketStatisticsDailyDao.upsert_by_scope(
                db,
                target_date,
                {
                    **payload,
                    "snapshot_scope": cls.SCOPE_LEAF,
                    "project_id": project_id,
                    "project_name": project_name_map.get(project_id, ""),
                    "module_id": module_id,
                    "module_name": str(getattr(sample, "module_name", None) or "").strip(),
                    "module_code": module_code_map.get(module_id, ""),
                    "issue_type_id": issue_type_id,
                    "issue_type_name": str(getattr(sample, "issue_type_name", None) or "").strip(),
                },
                snapshot_scope=cls.SCOPE_LEAF,
                project_id=project_id,
                module_id=module_id,
                issue_type_id=issue_type_id,
            )
            leaf_count += 1
        submitted_rows = [
            ticket for ticket in rows
            if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), begin_time, end_time)
        ]
        revision = TicketCustomMetricService.definition_revision(
            TicketCustomMetricService.get_definitions(db).get("metrics")
        )
        metric_rows = TicketCustomMetricService.build_snapshot_rows(db, submitted_rows, cls.SCOPE_ALL, revision)
        metric_rows.extend(TicketCustomMetricService.build_snapshot_rows(db, submitted_rows, cls.SCOPE_LEAF, revision))
        TicketStatisticsMetricSnapshotDao.replace_snapshot_rows(db, "daily", target_date.isoformat(), metric_rows)
        db.commit()
        logger.info(
            f"工单每日快照已生成 | statistics_date={target_date}, "
            f"submitted_count={all_payload['submitted_count']}, leaf_count={leaf_count}"
        )
        return {"statisticsDate": target_date.isoformat(), "leafCount": leaf_count, **all_payload}

    @classmethod
    def build_business_week_snapshot(
        cls,
        db: Session,
        period_start_time: datetime | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        生成并落库一个完整业务周的工单快照。
        :param db: 数据库会话。
        :param period_start_time: 业务周开始时间；为空时取上一完整业务周。
        :param config: 业务周配置；为空时读取系统参数。
        :return: 写入摘要。
        """
        active_config = TicketStatisticsTimeUtil.normalize_config(config or TicketStatisticsTimeUtil.get_config(db))
        if isinstance(period_start_time, datetime):
            start_time = period_start_time.replace(microsecond=0)
        else:
            start_time, _ = TicketStatisticsTimeUtil.get_business_week_range(
                active_config,
                datetime.now(),
                "previous_completed",
            )
        period_end_time = start_time + timedelta(days=7) - timedelta(seconds=1)
        rows = TicketProcessingStatsDao.list_trend_tickets(
            db,
            end_time=period_end_time,
            project_ids=None,
            module_ids=None,
            module_codes=None,
        )
        module_code_map = TicketStatisticsPeriodSnapshotDao.build_module_code_map(
            db,
            [int(ticket.module_id) for ticket in rows if getattr(ticket, "module_id", None)],
        )
        project_name_map = TicketStatisticsPeriodSnapshotDao.build_project_name_map(
            db,
            [int(ticket.project_id) for ticket in rows if getattr(ticket, "project_id", None)],
        )
        all_payload = cls.build_metric_payload(rows, start_time, period_end_time)
        TicketStatisticsPeriodSnapshotDao.upsert_by_scope(
            db,
            cls.PERIOD_TYPE_BUSINESS_WEEK,
            start_time,
            period_end_time,
            {
                **all_payload,
                "period_key": start_time.date().isoformat(),
                "snapshot_scope": cls.SCOPE_ALL,
                "project_id": 0,
                "project_name": "",
                "module_id": 0,
                "module_name": "",
                "module_code": "",
                "issue_type_id": "",
                "issue_type_name": "",
            },
            snapshot_scope=cls.SCOPE_ALL,
        )
        leaf_count = 0
        for dimension_rows in cls.group_leaf_rows(rows).values():
            sample = dimension_rows[0]
            project_id = int(getattr(sample, "project_id", None) or 0)
            module_id = int(getattr(sample, "module_id", None) or 0)
            issue_type_id = str(getattr(sample, "issue_type_id", None) or "").strip()
            payload = cls.build_metric_payload(dimension_rows, start_time, period_end_time)
            TicketStatisticsPeriodSnapshotDao.upsert_by_scope(
                db,
                cls.PERIOD_TYPE_BUSINESS_WEEK,
                start_time,
                period_end_time,
                {
                    **payload,
                    "period_key": start_time.date().isoformat(),
                    "snapshot_scope": cls.SCOPE_LEAF,
                    "project_id": project_id,
                    "project_name": project_name_map.get(project_id, ""),
                    "module_id": module_id,
                    "module_name": str(getattr(sample, "module_name", None) or "").strip(),
                    "module_code": module_code_map.get(module_id, ""),
                    "issue_type_id": issue_type_id,
                    "issue_type_name": str(getattr(sample, "issue_type_name", None) or "").strip(),
                },
                snapshot_scope=cls.SCOPE_LEAF,
                project_id=project_id,
                module_id=module_id,
                issue_type_id=issue_type_id,
            )
            leaf_count += 1
        submitted_rows = [
            ticket for ticket in rows
            if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), start_time, period_end_time)
        ]
        revision = TicketCustomMetricService.definition_revision(
            TicketCustomMetricService.get_definitions(db).get("metrics")
        )
        metric_rows = TicketCustomMetricService.build_snapshot_rows(db, submitted_rows, cls.SCOPE_ALL, revision)
        metric_rows.extend(TicketCustomMetricService.build_snapshot_rows(db, submitted_rows, cls.SCOPE_LEAF, revision))
        TicketStatisticsMetricSnapshotDao.replace_snapshot_rows(db, "business_week", start_time.date().isoformat(), metric_rows)
        db.commit()
        logger.info(
            f"工单业务周快照已生成 | period_start={start_time}, period_end={period_end_time}, "
            f"submitted_count={all_payload['submitted_count']}, leaf_count={leaf_count}"
        )
        return {
            "periodType": cls.PERIOD_TYPE_BUSINESS_WEEK,
            "periodStartTime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "periodEndTime": period_end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "periodKey": start_time.date().isoformat(),
            "leafCount": leaf_count,
            **all_payload,
        }

    @classmethod
    def build_metric_payload(
        cls,
        rows: list[Ticket],
        begin_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """
        按指定工单集合构造快照指标。
        :param rows: 工单集合。
        :param begin_time: 统计日开始时间。
        :param end_time: 统计日结束时间。
        :return: 可写入快照表的指标字典。
        """
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
        submitted_count = len(submitted_rows)
        payload = {
            "total_count": sum(
                1
                for ticket in rows
                if cls._in_range(TicketProcessingStatsDao.resolve_submit_time(ticket), None, end_time)
            ),
            "submitted_count": submitted_count,
            "new_count": submitted_count,
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
            "avg_process_seconds": cls._average_seconds(processed_rows, "processed_at"),
        }
        return payload

    @classmethod
    def group_leaf_rows(cls, rows: list[Ticket]) -> dict[tuple[int, int, str], list[Ticket]]:
        """
        按项目、模块、工单类型对工单分组。
        :param rows: 工单集合。
        :return: 叶子维度分组。
        """
        grouped: dict[tuple[int, int, str], list[Ticket]] = {}
        for ticket in rows:
            key = (
                int(getattr(ticket, "project_id", None) or 0),
                int(getattr(ticket, "module_id", None) or 0),
                str(getattr(ticket, "issue_type_id", None) or "").strip(),
            )
            grouped.setdefault(key, []).append(ticket)
        return grouped

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
