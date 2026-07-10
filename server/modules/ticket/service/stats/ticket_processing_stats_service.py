from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import (
    TicketDao,
    _bucket_label,
    _bucket_start,
    _date_end,
    _date_start,
    _normalize_granularity,
)
from modules.ticket.dao.ticket_processing_stats_dao import TicketProcessingStatsDao
from modules.ticket.dao.ticket_statistics_daily_dao import TicketStatisticsDailyDao
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
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


def _camelize(value: Any) -> Any:
    """
    递归转换统计接口返回字段为小驼峰。
    :param value: 字典、列表或普通值。
    :return: 小驼峰字段结果。
    """
    if isinstance(value, dict):
        return {CamelCaseUtil.snake_to_camel(str(key)): _camelize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    return value


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
        issue_type_ids: Any = None,
        statistics_mode: str | None = "realtime",
    ) -> dict:
        """
        获取处理口径 overview 统计。
        :param query_db: 数据库会话。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param project_ids: 项目ID多选。
        :param module_ids: 模块ID多选。
        :param module_codes: 模块业务码多选。
        :param issue_type_ids: 工单类型编码多选。
        :return: 小驼峰统计结果。
        """
        start = _date_start(begin_time)
        finish = _date_end(end_time)
        project_id_values = _normalize_int_list(project_ids)
        module_id_values = _normalize_int_list(module_ids)
        module_code_values = _normalize_text_list(module_codes)
        issue_type_id_values = _normalize_text_list(issue_type_ids)
        normalized_mode = str(statistics_mode or "realtime").strip().lower()
        if normalized_mode == "snapshot":
            snapshot = cls.get_snapshot_statistics(
                query_db,
                start,
                finish,
                project_id_values,
                module_id_values,
                module_code_values,
                issue_type_id_values,
            )
            return _camelize(snapshot)
        base_statistics = _camelize(
            TicketDao.get_ticket_statistics(
                db=query_db,
                begin_time=start,
                end_time=finish,
                project_ids=project_id_values,
                module_ids=module_id_values,
                module_codes=module_code_values,
                issue_type_ids=issue_type_id_values,
            )
        )
        stat_options = TicketSyncConfigService.get_ticket_stat_classification_options(query_db)
        base_statistics = cls.normalize_overview_count_rows(base_statistics, stat_options)
        rows = TicketProcessingStatsDao.list_metric_tickets(
            query_db,
            begin_time=start,
            end_time=finish,
            project_ids=project_id_values,
            module_ids=module_id_values,
            module_codes=module_code_values,
            issue_type_ids=issue_type_id_values,
        )
        metrics = cls.build_overview_metrics(rows, start, finish)
        return {**base_statistics, **_camelize(metrics)}

    @classmethod
    def normalize_overview_count_rows(cls, statistics: dict, stat_options: dict[str, Any] | None = None) -> dict:
        """
        归一化 overview 汇总统计行，避免同一业务含义因空值或旧名称拆成多行。
        :param statistics: 已转换为小驼峰的 overview 统计结果。
        :param stat_options: 当前工单统计枚举配置。
        :return: 合并重复统计行后的 overview 统计结果。
        """
        if not isinstance(statistics, dict):
            return statistics
        options = stat_options if isinstance(stat_options, dict) else {}
        result = {**statistics}
        result["statusCounts"] = cls.merge_label_count_rows(result.get("statusCounts"), "status", "未填写")
        result["categoryCounts"] = cls.merge_label_count_rows(result.get("categoryCounts"), "category", "未分类")
        result["moduleCounts"] = cls.merge_label_count_rows(result.get("moduleCounts"), "module", "未填写")
        result["sourceCounts"] = cls.merge_label_count_rows(result.get("sourceCounts"), "source", "未填写")
        result["priorityCounts"] = cls.merge_label_count_rows(result.get("priorityCounts"), "priority", "未填写")
        result["rootCauseCounts"] = cls.merge_label_count_rows(result.get("rootCauseCounts"), "rootCause", "未填写")
        result["assigneeCounts"] = cls.merge_assignee_count_rows(result.get("assigneeCounts"))
        result["problemCounts"] = cls.merge_problem_count_rows(result.get("problemCounts"))
        result["transitionCounts"] = cls.merge_transition_count_rows(result.get("transitionCounts"))
        result["issueTypeCounts"] = cls.merge_code_name_count_rows(
            result.get("issueTypeCounts"),
            "issueTypeId",
            "issueTypeName",
            options.get("issueTypes"),
            "未填写",
        )
        result["rootCauseTypeCounts"] = cls.merge_option_value_count_rows(
            result.get("rootCauseTypeCounts"),
            "rootCauseType",
            options.get("rootCauseTypes"),
            "未填写",
        )
        result["solutionTypeCounts"] = cls.merge_option_value_count_rows(
            result.get("solutionTypeCounts"),
            "solutionType",
            options.get("solutionTypes"),
            "未填写",
        )
        result["resolutionCounts"] = cls.merge_code_name_count_rows(
            result.get("resolutionCounts"),
            "resolutionCode",
            "resolutionName",
            options.get("resolutions"),
            "未填写",
        )
        result["problemPatternCounts"] = cls.merge_code_name_count_rows(
            result.get("problemPatternCounts"),
            "problemPatternCode",
            "problemPatternName",
            options.get("problemPatterns"),
            "未填写",
        )
        return result

    @staticmethod
    def normalize_count_text(value: Any, blank_label: str = "未填写") -> str:
        """
        归一化统计行文本。
        :param value: 原始文本。
        :param blank_label: 空值占位文案。
        :return: 去除首尾空白后的文本，空值统一返回占位文案。
        """
        text = str(value or "").strip()
        return text if text and text != "未填写" else blank_label

    @classmethod
    def build_option_label_map(cls, rows: Any) -> dict[str, str]:
        """
        构造统计枚举 value 到 label 的映射。
        :param rows: 枚举配置数组。
        :return: value -> label 字典。
        """
        label_map: dict[str, str] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            value = str(row.get("value") or row.get("code") or "").strip()
            label = cls.normalize_count_text(row.get("label") or row.get("name") or value)
            if value:
                label_map[value] = label
        return label_map

    @classmethod
    def merge_label_count_rows(cls, rows: Any, field_name: str, blank_label: str = "未填写") -> list[dict[str, Any]]:
        """
        按单个展示字段合并统计行。
        :param rows: 原始统计行数组。
        :param field_name: 展示字段名。
        :param blank_label: 空值占位文案。
        :return: 合并后的统计行数组。
        """
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            label = cls.normalize_count_text(row.get(field_name), blank_label)
            if label not in row_map:
                row_map[label] = {**row, field_name: label, "count": 0}
            row_map[label]["count"] = int(row_map[label].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

    @classmethod
    def merge_option_value_count_rows(
        cls,
        rows: Any,
        field_name: str,
        option_rows: Any,
        blank_label: str = "未填写",
    ) -> list[dict[str, Any]]:
        """
        按单字段枚举值合并统计行，并统一空值占位。
        :param rows: 原始统计行数组。
        :param field_name: 枚举值字段名。
        :param option_rows: 当前枚举配置数组。
        :param blank_label: 空值占位文案。
        :return: 合并后的统计行数组。
        """
        label_map = cls.build_option_label_map(option_rows)
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            value = str(row.get(field_name) or "").strip()
            key = value or blank_label
            display_value = value or blank_label
            if key not in row_map:
                row_map[key] = {
                    **row,
                    field_name: display_value,
                    "label": label_map.get(value, display_value),
                    "count": 0,
                }
            row_map[key]["count"] = int(row_map[key].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

    @classmethod
    def merge_code_name_count_rows(
        cls,
        rows: Any,
        code_field: str,
        name_field: str,
        option_rows: Any,
        blank_label: str = "未填写",
    ) -> list[dict[str, Any]]:
        """
        按稳定编码优先合并 code/name 统计行，编码为空时按展示名称合并。
        :param rows: 原始统计行数组。
        :param code_field: 编码字段名。
        :param name_field: 名称字段名。
        :param option_rows: 当前枚举配置数组。
        :param blank_label: 空值占位文案。
        :return: 合并后的统计行数组。
        """
        label_map = cls.build_option_label_map(option_rows)
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            code = str(row.get(code_field) or "").strip()
            fallback_name = cls.normalize_count_text(row.get(name_field) or code, blank_label)
            name = label_map.get(code, fallback_name) if code else fallback_name
            key = f"code:{code}" if code else f"name:{name}"
            if key not in row_map:
                row_map[key] = {**row, code_field: code, name_field: name, "count": 0}
            row_map[key]["count"] = int(row_map[key].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

    @classmethod
    def merge_problem_count_rows(cls, rows: Any) -> list[dict[str, Any]]:
        """
        按真实问题布尔值合并统计行。
        :param rows: 原始问题性质统计行数组。
        :return: 合并后的统计行数组。
        """
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            value = row.get("isProblem")
            key = "true" if value is True else ("false" if value is False else "unknown")
            label = "真实问题" if value is True else ("非问题" if value is False else "未填写")
            if key not in row_map:
                row_map[key] = {
                    **row,
                    "isProblem": value if isinstance(value, bool) else None,
                    "label": label,
                    "count": 0,
                }
            row_map[key]["count"] = int(row_map[key].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

    @classmethod
    def merge_assignee_count_rows(cls, rows: Any) -> list[dict[str, Any]]:
        """
        按处理人 ID 优先合并人员处理量统计行，未分配人员按展示名合并。
        :param rows: 原始人员处理量统计行数组。
        :return: 合并后的统计行数组。
        """
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            user_id = row.get("userId")
            user_name = cls.normalize_count_text(row.get("userName"), "未指派")
            key = f"id:{user_id}" if user_id not in (None, "") else f"name:{user_name}"
            if key not in row_map:
                row_map[key] = {**row, "userName": user_name, "count": 0}
            row_map[key]["count"] = int(row_map[key].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

    @classmethod
    def merge_transition_count_rows(cls, rows: Any) -> list[dict[str, Any]]:
        """
        按状态流转起止状态合并统计行。
        :param rows: 原始状态流转统计行数组。
        :return: 合并后的统计行数组。
        """
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            from_status = cls.normalize_count_text(row.get("fromStatus"), "创建")
            to_status = cls.normalize_count_text(row.get("toStatus"), "未填写")
            key = f"{from_status}->{to_status}"
            if key not in row_map:
                row_map[key] = {**row, "fromStatus": from_status, "toStatus": to_status, "count": 0}
            row_map[key]["count"] = int(row_map[key].get("count") or 0) + int(row.get("count") or 0)
        return list(row_map.values())

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
        issue_type_ids: Any = None,
        problem_pattern_codes: Any = None,
        statistics_mode: str | None = "realtime",
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
        :param issue_type_ids: 工单类型编码多选。
        :param problem_pattern_codes: 细分问题编码多选。
        :return: 小驼峰趋势结果。
        """
        start = _date_start(begin_time)
        finish = _date_end(end_time)
        normalized_granularity = _normalize_granularity(granularity)
        project_id_values = _normalize_int_list(project_ids)
        module_id_values = _normalize_int_list(module_ids)
        module_code_values = _normalize_text_list(module_codes)
        issue_type_id_values = _normalize_text_list(issue_type_ids)
        problem_pattern_code_values = _normalize_text_list(problem_pattern_codes)
        normalized_mode = str(statistics_mode or "realtime").strip().lower()
        if normalized_mode == "snapshot":
            snapshot_trend = cls.get_snapshot_trend(
                query_db,
                start,
                finish,
                normalized_granularity,
                project_id_values,
                module_id_values,
                module_code_values,
                issue_type_id_values,
            )
            return _camelize(snapshot_trend)
        base_trend = _camelize(
            TicketDao.get_statistics_trend(
                db=query_db,
                begin_time=start,
                end_time=finish,
                project_ids=project_id_values,
                module_ids=module_id_values,
                module_codes=module_code_values,
                granularity=normalized_granularity,
                problem_pattern_codes=problem_pattern_code_values,
                issue_type_ids=issue_type_id_values,
            )
        )
        rows = TicketProcessingStatsDao.list_trend_tickets(
            query_db,
            end_time=finish,
            project_ids=project_id_values,
            module_ids=module_id_values,
            module_codes=module_code_values,
            issue_type_ids=issue_type_id_values,
            problem_pattern_codes=problem_pattern_code_values,
        )
        processing_trend = _camelize(cls.build_trend_metrics(rows, start, finish, normalized_granularity))
        return cls.merge_trend_series(base_trend, processing_trend, normalized_granularity)

    @classmethod
    def get_snapshot_statistics(
        cls,
        query_db: Session,
        begin_time: datetime | None,
        end_time: datetime | None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
    ) -> dict:
        """
        获取每日快照口径的 overview 统计。
        :param query_db: 数据库会话。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param project_ids: 项目ID过滤。
        :param module_ids: 模块ID过滤。
        :param module_codes: 模块业务码过滤。
        :param issue_type_ids: 工单类型编码过滤。
        :return: snake_case 统计结果。
        """
        begin_date = begin_time.date() if isinstance(begin_time, datetime) else None
        end_date = end_time.date() if isinstance(end_time, datetime) else None
        use_leaf_scope = bool(project_ids or module_ids or module_codes or issue_type_ids)
        rows = TicketStatisticsDailyDao.list_between(
            query_db,
            begin_date,
            end_date,
            snapshot_scope="leaf" if use_leaf_scope else "all",
            project_ids=project_ids if use_leaf_scope else None,
            module_ids=module_ids if use_leaf_scope else None,
            module_codes=module_codes if use_leaf_scope else None,
            issue_type_ids=issue_type_ids if use_leaf_scope else None,
        )
        leaf_rows = rows if use_leaf_scope else TicketStatisticsDailyDao.list_between(
            query_db,
            begin_date,
            end_date,
            snapshot_scope="leaf",
        )
        if not rows:
            return {
                "total": 0,
                "submitted_count": 0,
                "first_responded_count": 0,
                "processed_count": 0,
                "processed_in_new_count": 0,
                "process_rate": 0,
                "resolved_count": 0,
                "closed_count": 0,
                "unprocessed_count": 0,
                "processed_status_counts": [],
                "avg_first_response_seconds": 0,
                "avg_first_process_seconds": 0,
                "avg_resolve_seconds": 0,
                "avg_close_seconds": 0,
            }
        latest_rows = cls._latest_snapshot_rows(rows)
        latest_leaf_rows = cls._latest_snapshot_rows(leaf_rows)
        submitted_count = sum(int(row.submitted_count or 0) for row in rows)
        first_responded_count = sum(int(row.first_responded_count or 0) for row in rows)
        processed_count = sum(int(row.processed_count or 0) for row in rows)
        processed_in_new_count = sum(int(row.processed_in_new_count or 0) for row in rows)
        resolved_count = sum(int(row.resolved_count or 0) for row in rows)
        closed_count = sum(int(row.closed_count or 0) for row in rows)
        total_count = sum(int(row.total_count or 0) for row in latest_rows)
        unprocessed_backlog = sum(int(row.unprocessed_backlog or 0) for row in latest_rows)
        return {
            "total": total_count,
            "submitted_count": submitted_count,
            "first_responded_count": first_responded_count,
            "processed_count": processed_count,
            "processed_in_new_count": processed_in_new_count,
            "process_rate": round(processed_in_new_count / submitted_count, 4) if submitted_count else 0,
            "resolved_count": resolved_count,
            "closed_count": closed_count,
            "unprocessed_count": unprocessed_backlog,
            "processed_status_counts": [
                {"status": "processed", "label": "已处理", "count": processed_in_new_count},
                {"status": "unprocessed", "label": "未处理", "count": unprocessed_backlog},
            ],
            "avg_first_response_seconds": cls._weighted_snapshot_seconds(
                rows, "avg_first_response_seconds", "first_responded_count"
            ),
            "avg_first_process_seconds": cls._weighted_snapshot_seconds(
                rows, "avg_first_process_seconds", "processed_count"
            ),
            "avg_resolve_seconds": cls._weighted_snapshot_seconds(rows, "avg_resolve_seconds", "resolved_count"),
            "avg_close_seconds": cls._weighted_snapshot_seconds(rows, "avg_close_seconds", "closed_count"),
            "module_counts": cls._snapshot_count_rows(latest_leaf_rows, "module_name", "module"),
            "issue_type_counts": cls._snapshot_code_name_rows(latest_leaf_rows, "issue_type_id", "issue_type_name"),
        }

    @classmethod
    def get_snapshot_trend(
        cls,
        query_db: Session,
        begin_time: datetime | None,
        end_time: datetime | None,
        granularity: str,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
    ) -> dict:
        """
        获取每日快照口径的趋势统计。
        :param query_db: 数据库会话。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :param granularity: 趋势粒度。
        :param project_ids: 项目ID过滤。
        :param module_ids: 模块ID过滤。
        :param module_codes: 模块业务码过滤。
        :param issue_type_ids: 工单类型编码过滤。
        :return: snake_case 趋势结果。
        """
        begin_date = begin_time.date() if isinstance(begin_time, datetime) else None
        end_date = end_time.date() if isinstance(end_time, datetime) else None
        use_leaf_scope = bool(project_ids or module_ids or module_codes or issue_type_ids)
        rows = TicketStatisticsDailyDao.list_between(
            query_db,
            begin_date,
            end_date,
            snapshot_scope="leaf" if use_leaf_scope else "all",
            project_ids=project_ids if use_leaf_scope else None,
            module_ids=module_ids if use_leaf_scope else None,
            module_codes=module_codes if use_leaf_scope else None,
            issue_type_ids=issue_type_ids if use_leaf_scope else None,
        )
        leaf_rows = rows if use_leaf_scope else TicketStatisticsDailyDao.list_between(
            query_db,
            begin_date,
            end_date,
            snapshot_scope="leaf",
        )
        if not rows:
            return {"granularity": granularity, "series": []}
        bucket_map: dict[str, dict[str, Any]] = {}
        bucket_rows: dict[str, list[Any]] = {}
        bucket_leaf_rows: dict[str, list[Any]] = {}
        for row in rows:
            bucket_date = _bucket_start(datetime.combine(row.statistics_date, time.min), granularity)
            bucket_key = _bucket_label(bucket_date, granularity)
            bucket = bucket_map.setdefault(
                bucket_key,
                {
                    "bucket": bucket_key,
                    "new_count": 0,
                    "first_responded_count": 0,
                    "processed_count": 0,
                    "processed_in_new_count": 0,
                    "resolved_count": 0,
                    "closed_count": 0,
                    "unprocessed_backlog": 0,
                    "open_backlog": 0,
                    "avg_first_response_seconds": 0,
                    "avg_first_process_seconds": 0,
                    "problem_count": 0,
                    "non_problem_count": 0,
                    "support_count": 0,
                    "module_counts": [],
                    "issue_type_counts": [],
                    "problem_pattern_counts": [],
                },
            )
            bucket_rows.setdefault(bucket_key, []).append(row)
            bucket["new_count"] += int(row.submitted_count or 0)
            bucket["first_responded_count"] += int(row.first_responded_count or 0)
            bucket["processed_count"] += int(row.processed_count or 0)
            bucket["processed_in_new_count"] += int(row.processed_in_new_count or 0)
            bucket["resolved_count"] += int(row.resolved_count or 0)
            bucket["closed_count"] += int(row.closed_count or 0)
        for row in leaf_rows:
            bucket_date = _bucket_start(datetime.combine(row.statistics_date, time.min), granularity)
            bucket_key = _bucket_label(bucket_date, granularity)
            bucket_leaf_rows.setdefault(bucket_key, []).append(row)
        series = list(bucket_map.values())
        for bucket in series:
            bucket_key = str(bucket.get("bucket") or "")
            rows_in_bucket = bucket_rows.get(bucket_key, [])
            leaf_rows_in_bucket = bucket_leaf_rows.get(bucket_key, [])
            latest_rows = cls._latest_snapshot_rows(rows_in_bucket)
            latest_leaf_rows = cls._latest_snapshot_rows(leaf_rows_in_bucket)
            bucket["unprocessed_backlog"] = sum(int(row.unprocessed_backlog or 0) for row in latest_rows)
            bucket["open_backlog"] = sum(int(row.open_backlog or 0) for row in latest_rows)
            bucket["avg_first_response_seconds"] = cls._weighted_snapshot_seconds(
                rows_in_bucket, "avg_first_response_seconds", "first_responded_count"
            )
            bucket["avg_first_process_seconds"] = cls._weighted_snapshot_seconds(
                rows_in_bucket, "avg_first_process_seconds", "processed_count"
            )
            bucket["module_counts"] = cls._snapshot_count_rows(latest_leaf_rows, "module_name", "name")
            bucket["issue_type_counts"] = cls._snapshot_count_rows(latest_leaf_rows, "issue_type_name", "name")
            bucket["process_rate"] = (
                round(bucket["processed_in_new_count"] / bucket["new_count"], 4) if bucket["new_count"] else 0
            )
            bucket["net_increase"] = bucket["new_count"] - bucket["closed_count"]
        return {"granularity": granularity, "series": series}

    @staticmethod
    def _weighted_snapshot_seconds(rows: list[Any], field_name: str, weight_field_name: str) -> int:
        """
        按事件数量加权计算快照耗时。
        :param rows: 快照行列表。
        :param field_name: 字段名。
        :param weight_field_name: 权重字段名。
        :return: 平均秒数。
        """
        total_weight = 0
        total_seconds = 0
        for row in rows:
            seconds = int(getattr(row, field_name, 0) or 0)
            weight = int(getattr(row, weight_field_name, 0) or 0)
            if seconds <= 0 or weight <= 0:
                continue
            total_weight += weight
            total_seconds += seconds * weight
        return int(total_seconds / total_weight) if total_weight else 0

    @staticmethod
    def _latest_snapshot_rows(rows: list[Any]) -> list[Any]:
        """
        获取快照集合中最后日期的所有维度行。
        :param rows: 快照行列表。
        :return: 最后日期对应的行列表。
        """
        if not rows:
            return []
        latest_date = max(row.statistics_date for row in rows)
        return [row for row in rows if row.statistics_date == latest_date]

    @classmethod
    def _snapshot_count_rows(cls, rows: list[Any], field_name: str, result_field_name: str) -> list[dict[str, Any]]:
        """
        把快照维度字段聚合为统计行。
        :param rows: 快照行列表。
        :param field_name: 维度字段名。
        :param result_field_name: 返回统计字段名。
        :return: 统计行。
        """
        counter: dict[str, int] = {}
        for row in rows:
            label = cls.normalize_count_text(getattr(row, field_name, ""), "未填写")
            counter[label] = counter.get(label, 0) + int(getattr(row, "total_count", 0) or 0)
        return [{result_field_name: key, "count": value} for key, value in counter.items()]

    @classmethod
    def _snapshot_code_name_rows(
        cls,
        rows: list[Any],
        code_field_name: str,
        name_field_name: str,
    ) -> list[dict[str, Any]]:
        """
        把快照 code/name 维度聚合为统计行。
        :param rows: 快照行列表。
        :param code_field_name: 编码字段名。
        :param name_field_name: 名称字段名。
        :return: code/name 统计行。
        """
        row_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            code = str(getattr(row, code_field_name, "") or "").strip()
            name = cls.normalize_count_text(getattr(row, name_field_name, "") or code, "未填写")
            key = f"code:{code}" if code else f"name:{name}"
            if key not in row_map:
                row_map[key] = {"issue_type_id": code, "issue_type_name": name, "count": 0}
            row_map[key]["count"] += int(getattr(row, "total_count", 0) or 0)
        return list(row_map.values())

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
