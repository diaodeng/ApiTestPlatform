from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao, _date_end, _date_start, _normalize_granularity
from modules.ticket.dao.ticket_processing_stats_dao import TicketProcessingStatsDao
from utils.common_util import CamelCaseUtil


def _normalize_int_list(value: Any) -> list[int]:
    """
    将统计查询参数归一化为整数列表。
    :param value: 逗号分隔字符串、数组或单值。
    :return: 整数列表。
    """
    if value is None or value == "":
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    result: list[int] = []
    for item in raw_items:
        try:
            parsed = int(str(item or "").strip())
        except ValueError:
            continue
        if parsed not in result:
            result.append(parsed)
    return result


def _normalize_text_list(value: Any) -> list[str]:
    """
    将统计查询参数归一化为文本列表。
    :param value: 逗号分隔字符串、数组或单值。
    :return: 文本列表。
    """
    if value is None or value == "":
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    result: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


class TicketProcessingStatsService:
    """
    工单处理口径统计服务。

    负责计算提交、响应、处理、处置、关闭和存量指标；基础分类分布仍复用既有统计口径保持兼容。
    """

    @classmethod
    def get_statistics(
        cls,
        query_db: Session,
        begin_time=None,
        end_time=None,
        project_ids: Any = None,
        module_ids: Any = None,
        module_codes: Any = None,
    ) -> dict:
        """
        获取处理口径 overview 统计。
        :param query_db: 数据库会话。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param project_ids: 项目ID多选。
        :param module_ids: 模块ID多选。
        :param module_codes: 模块业务码多选。
        :return: 小驼峰统计结果。
        """
        start = _date_start(begin_time)
        finish = _date_end(end_time)
        project_id_values = _normalize_int_list(project_ids)
        module_id_values = _normalize_int_list(module_ids)
        module_code_values = _normalize_text_list(module_codes)
        base_statistics = CamelCaseUtil.transform_result(
            TicketDao.get_ticket_statistics(
                query_db,
                start,
                finish,
                project_id_values,
                module_id_values,
                module_code_values,
            )
        )
        rows = TicketProcessingStatsDao.list_metric_tickets(
            query_db,
            begin_time=start,
            end_time=finish,
            project_ids=project_id_values,
            module_ids=module_id_values,
            module_codes=module_code_values,
        )
        metrics = cls.build_overview_metrics(rows, start, finish)
        return {**base_statistics, **CamelCaseUtil.transform_result(metrics)}

    @classmethod
    def get_statistics_trend(
        cls,
        query_db: Session,
        begin_time=None,
        end_time=None,
        project_ids: Any = None,
        module_ids: Any = None,
        module_codes: Any = None,
        granularity: str | None = "week",
        problem_pattern_codes: Any = None,
    ) -> dict:
        """
        获取处理口径趋势统计。
        :param query_db: 数据库会话。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param project_ids: 项目ID多选。
        :param module_ids: 模块ID多选。
        :param module_codes: 模块业务码多选。
        :param granularity: day/week/month。
        :param problem_pattern_codes: 细分问题编码多选。
        :return: 小驼峰趋势结果。
        """
        start = _date_start(begin_time)
        finish = _date_end(end_time)
        normalized_granularity = _normalize_granularity(granularity)
        project_id_values = _normalize_int_list(project_ids)
        module_id_values = _normalize_int_list(module_ids)
        module_code_values = _normalize_text_list(module_codes)
        problem_pattern_code_values = _normalize_text_list(problem_pattern_codes)
        base_trend = CamelCaseUtil.transform_result(
            TicketDao.get_statistics_trend(
                query_db,
                start,
                finish,
                project_id_values,
                module_id_values,
                module_code_values,
                normalized_granularity,
                problem_pattern_code_values,
            )
        )
        rows = TicketProcessingStatsDao.list_trend_tickets(
            query_db,
            end_time=finish,
            project_ids=project_id_values,
            module_ids=module_id_values,
            module_codes=module_code_values,
            problem_pattern_codes=problem_pattern_code_values,
        )
        processing_trend = CamelCaseUtil.transform_result(
            cls.build_trend_metrics(rows, start, finish, normalized_granularity)
        )
        return cls.merge_trend_series(base_trend, processing_trend, normalized_granularity)

    @staticmethod
    def merge_trend_series(base_trend: dict, processing_trend: dict, granularity: str) -> dict:
        """
        合并原有趋势字段和新增处理口径字段，避免新增处理统计时丢失旧曲线数据。
        :param base_trend: 原有趋势统计结果。
        :param processing_trend: 处理口径趋势统计结果。
        :param granularity: 趋势粒度。
        :return: 合并后的趋势统计。
        """
        base_rows = base_trend.get("series") if isinstance(base_trend.get("series"), list) else []
        processing_rows = (
            processing_trend.get("series") if isinstance(processing_trend.get("series"), list) else []
        )
        processing_map = {str(row.get("bucket") or ""): row for row in processing_rows if isinstance(row, dict)}
        processing_only_fields = (
            "firstRespondedCount",
            "processedCount",
            "processedInNewCount",
            "processRate",
            "unprocessedBacklog",
            "avgFirstResponseSeconds",
            "avgFirstProcessSeconds",
        )
        merged_rows = []
        seen_buckets = set()
        for row in base_rows:
            if not isinstance(row, dict):
                continue
            bucket = str(row.get("bucket") or "")
            seen_buckets.add(bucket)
            merged_row = {**row}
            processing_row = processing_map.get(bucket) or {}
            for field_name in processing_only_fields:
                if field_name in processing_row:
                    merged_row[field_name] = processing_row[field_name]
            merged_rows.append(merged_row)
        for row in processing_rows:
            bucket = str(row.get("bucket") or "")
            if bucket and bucket not in seen_buckets:
                merged_rows.append(row)
        return {
            "granularity": base_trend.get("granularity") or processing_trend.get("granularity") or granularity,
            "series": merged_rows,
        }

    @classmethod
    def build_overview_metrics(
        cls,
        rows: list[Any],
        begin_time: datetime | None,
        end_time: datetime | None,
    ) -> dict:
        """
        基于工单列表计算 overview 处理指标。
        :param rows: 工单列表。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :return: snake_case 指标。
        """
        submitted_rows = [
            ticket for ticket in rows if cls.time_in_range(cls.submit_time(ticket), begin_time, end_time)
        ]
        first_responded_rows = [
            ticket for ticket in rows if cls.time_in_range(ticket.first_response_at, begin_time, end_time)
        ]
        processed_rows = [ticket for ticket in rows if cls.time_in_range(ticket.processed_at, begin_time, end_time)]
        resolved_rows = [ticket for ticket in rows if cls.time_in_range(ticket.resolved_at, begin_time, end_time)]
        closed_rows = [ticket for ticket in rows if cls.time_in_range(ticket.closed_at, begin_time, end_time)]
        processed_in_new_rows = [ticket for ticket in submitted_rows if ticket.processed_at is not None]
        unprocessed_count = sum(1 for ticket in submitted_rows if ticket.processed_at is None)
        new_count = len(submitted_rows)
        return {
            "new_count": new_count,
            "first_responded_count": len(first_responded_rows),
            "processed_count": len(processed_rows),
            "processed_in_new_count": len(processed_in_new_rows),
            "process_rate": round(len(processed_in_new_rows) / new_count, 4) if new_count else 0,
            "resolved_count": len(resolved_rows),
            "closed_count": len(closed_rows),
            "unprocessed_count": unprocessed_count,
            "processed_status_counts": [
                {"status": "processed", "label": "已处理", "count": len(processed_in_new_rows)},
                {"status": "unprocessed", "label": "未处理", "count": unprocessed_count},
            ],
            "avg_first_response_seconds": cls.average_seconds(rows, "first_response_at"),
            "avg_first_process_seconds": cls.average_seconds(rows, "processed_at"),
            "avg_resolve_seconds": cls.average_seconds(rows, "resolved_at"),
            "avg_close_seconds": cls.average_seconds(rows, "closed_at"),
        }

    @classmethod
    def build_trend_metrics(
        cls,
        rows: list[Any],
        begin_time: datetime | None,
        end_time: datetime | None,
        granularity: str,
    ) -> dict:
        """
        基于工单列表计算处理趋势。
        :param rows: 工单列表。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param granularity: day/week/month。
        :return: snake_case 趋势结果。
        """
        event_times = [
            value
            for ticket in rows
            for value in (
                cls.submit_time(ticket),
                ticket.first_response_at,
                ticket.processed_at,
                ticket.resolved_at,
                ticket.closed_at,
            )
            if isinstance(value, datetime)
        ]
        if not event_times:
            return {"granularity": granularity, "series": []}
        start_time = begin_time or min(event_times)
        finish_time = end_time or max(event_times)
        bucket_map = cls.init_bucket_map(start_time, finish_time, granularity)
        for ticket in rows:
            submit_time = cls.submit_time(ticket)
            submit_bucket = cls.bucket_for_time(bucket_map, submit_time, granularity, begin_time, end_time)
            if submit_bucket:
                submit_bucket["new_count"] += 1
                if ticket.processed_at is not None:
                    submit_bucket["processed_in_new_count"] += 1
            for field_name, count_name in (
                ("first_response_at", "first_responded_count"),
                ("processed_at", "processed_count"),
                ("resolved_at", "resolved_count"),
                ("closed_at", "closed_count"),
            ):
                bucket = cls.bucket_for_time(bucket_map, getattr(ticket, field_name), granularity, begin_time, end_time)
                if bucket:
                    bucket[count_name] += 1
        series = []
        for bucket_date in sorted(bucket_map):
            bucket = bucket_map[bucket_date]
            next_bucket_time = datetime.combine(cls.next_bucket_start(bucket_date, granularity), time.min)
            bucket["process_rate"] = (
                round(bucket["processed_in_new_count"] / bucket["new_count"], 4) if bucket["new_count"] else 0
            )
            bucket["unprocessed_backlog"] = sum(
                1
                for ticket in rows
                if isinstance(cls.submit_time(ticket), datetime)
                and cls.submit_time(ticket) < next_bucket_time
                and (not isinstance(ticket.processed_at, datetime) or ticket.processed_at >= next_bucket_time)
            )
            bucket["open_backlog"] = sum(
                1
                for ticket in rows
                if isinstance(cls.submit_time(ticket), datetime)
                and cls.submit_time(ticket) < next_bucket_time
                and (not isinstance(ticket.closed_at, datetime) or ticket.closed_at >= next_bucket_time)
            )
            bucket["net_increase"] = bucket["new_count"] - bucket["closed_count"]
            response_rows = [
                ticket
                for ticket in rows
                if cls.bucket_for_time(
                    bucket_map, ticket.first_response_at, granularity, begin_time, end_time
                )
                is bucket
            ]
            process_rows = [
                ticket
                for ticket in rows
                if cls.bucket_for_time(bucket_map, ticket.processed_at, granularity, begin_time, end_time)
                is bucket
            ]
            bucket["avg_first_response_seconds"] = cls.average_seconds(response_rows, "first_response_at")
            bucket["avg_first_process_seconds"] = cls.average_seconds(process_rows, "processed_at")
            series.append(bucket)
        return {"granularity": granularity, "series": series}

    @staticmethod
    def time_in_range(value: datetime | None, begin_time: datetime | None, end_time: datetime | None) -> bool:
        """
        判断时间是否在统计范围内。
        :param value: 待判断时间。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :return: 是否命中。
        """
        if not isinstance(value, datetime):
            return False
        if begin_time and value < begin_time:
            return False
        if end_time and value > end_time:
            return False
        return True

    @staticmethod
    def submit_time(ticket: Any) -> datetime | None:
        """
        解析工单提交时间。
        :param ticket: 工单实体。
        :return: 提交时间。
        """
        return TicketProcessingStatsDao.resolve_submit_time(ticket)

    @classmethod
    def average_seconds(cls, rows: list[Any], target_field: str) -> int:
        """
        计算目标时间与 submit_time 的平均秒差。
        :param rows: 工单列表。
        :param target_field: 目标时间字段名。
        :return: 平均秒数。
        """
        values = []
        for ticket in rows:
            submit_time = cls.submit_time(ticket)
            target_time = getattr(ticket, target_field, None)
            if isinstance(submit_time, datetime) and isinstance(target_time, datetime) and target_time >= submit_time:
                values.append(int((target_time - submit_time).total_seconds()))
        return int(sum(values) / len(values)) if values else 0

    @classmethod
    def init_bucket_map(
        cls,
        start_time: datetime,
        finish_time: datetime,
        granularity: str,
    ) -> dict[date, dict[str, Any]]:
        """
        初始化趋势桶。
        :param start_time: 开始时间。
        :param finish_time: 结束时间。
        :param granularity: day/week/month。
        :return: 趋势桶映射。
        """
        bucket_map: dict[date, dict[str, Any]] = {}
        current_bucket = cls.bucket_start(start_time, granularity)
        finish_bucket = cls.bucket_start(finish_time, granularity)
        while current_bucket <= finish_bucket:
            bucket_map[current_bucket] = {
                "bucket": cls.bucket_label(current_bucket, granularity),
                "bucket_start": current_bucket.isoformat(),
                "new_count": 0,
                "first_responded_count": 0,
                "processed_count": 0,
                "processed_in_new_count": 0,
                "process_rate": 0,
                "resolved_count": 0,
                "closed_count": 0,
                "net_increase": 0,
                "open_backlog": 0,
                "unprocessed_backlog": 0,
                "avg_first_response_seconds": 0,
                "avg_first_process_seconds": 0,
            }
            current_bucket = cls.next_bucket_start(current_bucket, granularity)
        return bucket_map

    @staticmethod
    def bucket_start(value: datetime, granularity: str) -> date:
        """
        计算时间桶开始日期。
        :param value: 原始时间。
        :param granularity: day/week/month。
        :return: 桶开始日期。
        """
        current_date = value.date()
        if granularity == "month":
            return current_date.replace(day=1)
        if granularity == "week":
            return current_date - timedelta(days=current_date.weekday())
        return current_date

    @staticmethod
    def bucket_label(bucket_date: date, granularity: str) -> str:
        """
        格式化时间桶标签。
        :param bucket_date: 桶日期。
        :param granularity: day/week/month。
        :return: 标签。
        """
        if granularity == "month":
            return bucket_date.strftime("%Y-%m")
        if granularity == "week":
            iso_year, iso_week, _ = bucket_date.isocalendar()
            return f"{iso_year}-W{iso_week:02d}"
        return bucket_date.strftime("%Y-%m-%d")

    @staticmethod
    def next_bucket_start(bucket_date: date, granularity: str) -> date:
        """
        计算下一个桶开始日期。
        :param bucket_date: 当前桶日期。
        :param granularity: day/week/month。
        :return: 下一个桶日期。
        """
        if granularity == "month":
            year = bucket_date.year + (1 if bucket_date.month == 12 else 0)
            month = 1 if bucket_date.month == 12 else bucket_date.month + 1
            return date(year, month, 1)
        if granularity == "week":
            return bucket_date + timedelta(days=7)
        return bucket_date + timedelta(days=1)

    @classmethod
    def bucket_for_time(
        cls,
        bucket_map: dict[date, dict[str, Any]],
        value: datetime | None,
        granularity: str,
        begin_time: datetime | None,
        end_time: datetime | None,
    ) -> dict[str, Any] | None:
        """
        获取指定时间所属趋势桶。
        :param bucket_map: 趋势桶映射。
        :param value: 时间。
        :param granularity: day/week/month。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :return: 趋势桶或 None。
        """
        if not cls.time_in_range(value, begin_time, end_time):
            return None
        return bucket_map.get(cls.bucket_start(value, granularity))
