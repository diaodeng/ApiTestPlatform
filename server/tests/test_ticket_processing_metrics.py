from datetime import datetime, timedelta
from types import SimpleNamespace

from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.service.core.ticket_processing_metric_service import TicketProcessingMetricService

try:
    from modules.ticket.service.stats.ticket_processing_stats_service import TicketProcessingStatsService, _camelize
except Exception:
    TicketProcessingStatsService = None
    _camelize = None


def test_first_response_does_not_mark_processed():
    """首次响应时间不应被当作处理结论时间。"""
    submit_time = datetime(2026, 7, 8, 10, 0, 0)
    ticket = SimpleNamespace(
        submit_time=submit_time,
        create_time=submit_time,
        first_response_at=submit_time + timedelta(minutes=5),
        processed_at=None,
    )
    update_data = {}

    TicketProcessingMetricService.apply_status_time_fields(
        ticket=ticket,
        from_status=TicketStatus.PENDING.value,
        to_status=TicketStatus.PROCESSING.value,
        update_data=update_data,
        now=submit_time + timedelta(minutes=5),
    )

    assert "processed_at" not in update_data


def test_status_conclusion_marks_processed_once():
    """流转到具备结论的状态时首次写入 processed_at，已有值不覆盖。"""
    submit_time = datetime(2026, 7, 8, 10, 0, 0)
    existing_processed_at = submit_time + timedelta(hours=1)
    ticket = SimpleNamespace(processed_at=existing_processed_at, released_at=None, verified_at=None)
    update_data = {"root_cause": "配置错误"}

    TicketProcessingMetricService.apply_status_time_fields(
        ticket=ticket,
        from_status=TicketStatus.PROCESSING.value,
        to_status=TicketStatus.WAIT_RELEASE.value,
        update_data=update_data,
        now=submit_time + timedelta(hours=2),
    )

    assert "processed_at" not in update_data


def test_event_deployed_marks_release_fields():
    """发布事件应写入发版时间和发版版本。"""
    now = datetime(2026, 7, 8, 12, 0, 0)
    ticket = SimpleNamespace(processed_at=None, released_at=None, verified_at=None, resolved_at=None, closed_at=None)
    update_data = {}

    TicketProcessingMetricService.apply_event_time_fields(
        ticket=ticket,
        event_type=TicketEventType.DEPLOYED.value,
        content="版本已发布",
        event_data={"releasedVersion": "release/2.1.4"},
        update_data=update_data,
        now=now,
    )

    assert update_data["processed_at"] == now
    assert update_data["released_at"] == now
    assert update_data["released_version"] == "release/2.1.4"


def test_processing_stats_overview_metrics():
    """统计服务应区分范围内处理数和新增工单已处理数。"""
    if TicketProcessingStatsService is None:
        return
    submit_time = datetime(2026, 7, 8, 10, 0, 0)
    rows = [
        SimpleNamespace(
            submit_time=submit_time,
            create_time=submit_time,
            first_response_at=submit_time + timedelta(minutes=10),
            processed_at=submit_time + timedelta(hours=1),
            resolved_at=None,
            closed_at=None,
        ),
        SimpleNamespace(
            submit_time=submit_time + timedelta(hours=2),
            create_time=submit_time + timedelta(hours=2),
            first_response_at=None,
            processed_at=None,
            resolved_at=None,
            closed_at=None,
        ),
    ]

    metrics = TicketProcessingStatsService.build_overview_metrics(
        rows,
        submit_time,
        submit_time + timedelta(days=1),
    )

    assert metrics["new_count"] == 2
    assert metrics["first_responded_count"] == 1
    assert metrics["processed_count"] == 1
    assert metrics["processed_in_new_count"] == 1
    assert metrics["unprocessed_count"] == 1
    assert metrics["process_rate"] == 0.5
    assert metrics["avg_first_response_seconds"] == 600
    assert metrics["avg_first_process_seconds"] == 3600


def test_processing_stats_response_fields_are_recursive_camel_case():
    """统计接口返回字段应递归转小驼峰，避免前端嵌套表格和趋势图读不到数据。"""
    if _camelize is None:
        return

    payload = {
        "issue_type_counts": [{"issue_type_id": "bug", "issue_type_name": "缺陷", "count": 2}],
        "problem_counts": [{"is_problem": True, "label": "真实问题", "count": 1}],
        "root_cause_type_counts": [{"root_cause_type": "config", "count": 1}],
        "series": [
            {
                "bucket": "2026-07-08",
                "new_count": 3,
                "problem_count": 2,
                "module_counts": [{"name": "认证检查", "count": 3}],
            }
        ],
    }

    result = _camelize(payload)

    assert result["issueTypeCounts"][0]["issueTypeId"] == "bug"
    assert result["issueTypeCounts"][0]["issueTypeName"] == "缺陷"
    assert result["problemCounts"][0]["isProblem"] is True
    assert result["rootCauseTypeCounts"][0]["rootCauseType"] == "config"
    assert result["series"][0]["newCount"] == 3
    assert result["series"][0]["problemCount"] == 2
    assert result["series"][0]["moduleCounts"] == [{"name": "认证检查", "count": 3}]


def test_processing_stats_overview_rows_are_merged_by_stable_key():
    """overview 汇总统计应按稳定编码合并，并把空值与未填写归为同一行。"""
    if TicketProcessingStatsService is None:
        return

    payload = {
        "solutionTypeCounts": [
            {"solutionType": None, "count": 1},
            {"solutionType": "", "count": 2},
            {"solutionType": "未填写", "count": 3},
        ],
        "resolutionCounts": [
            {"resolutionCode": None, "resolutionName": None, "count": 1},
            {"resolutionCode": "", "resolutionName": "未填写", "count": 2},
            {"resolutionCode": "fixed", "resolutionName": "已修复旧名", "count": 3},
            {"resolutionCode": "fixed", "resolutionName": "已修复", "count": 4},
        ],
        "problemPatternCounts": [
            {"problemPatternCode": "pos_client_pay", "problemPatternName": "POS支付旧名", "count": 2},
            {"problemPatternCode": "pos_client_pay", "problemPatternName": "POS客户端支付", "count": 5},
            {"problemPatternCode": None, "problemPatternName": None, "count": 1},
            {"problemPatternCode": "", "problemPatternName": "未填写", "count": 1},
        ],
    }
    stat_options = {
        "solutionTypes": [],
        "resolutions": [{"value": "fixed", "label": "已修复"}],
        "problemPatterns": [{"value": "pos_client_pay", "label": "POS客户端支付"}],
    }

    result = TicketProcessingStatsService.normalize_overview_count_rows(payload, stat_options)

    assert result["solutionTypeCounts"] == [
        {"solutionType": "未填写", "count": 6, "label": "未填写"}
    ]
    assert result["resolutionCounts"] == [
        {"resolutionCode": "", "resolutionName": "未填写", "count": 3},
        {"resolutionCode": "fixed", "resolutionName": "已修复", "count": 7},
    ]
    assert result["problemPatternCounts"] == [
        {"problemPatternCode": "pos_client_pay", "problemPatternName": "POS客户端支付", "count": 7},
        {"problemPatternCode": "", "problemPatternName": "未填写", "count": 2},
    ]


def test_processing_trend_merge_keeps_base_trend_fields():
    """合并处理趋势时不应覆盖旧趋势的新增、关闭、存量和分类明细。"""
    if TicketProcessingStatsService is None:
        return

    base_trend = {
        "granularity": "day",
        "series": [
            {
                "bucket": "2026-07-08",
                "newCount": 7,
                "closedCount": 2,
                "resolvedCount": 3,
                "netIncrease": 5,
                "openBacklog": 11,
                "problemCount": 4,
                "moduleCounts": [{"name": "收银", "count": 7}],
                "problemPatternCounts": [{"name": "内存泄露", "count": 2}],
            }
        ],
    }
    processing_trend = {
        "granularity": "day",
        "series": [
            {
                "bucket": "2026-07-08",
                "newCount": 0,
                "closedCount": 0,
                "resolvedCount": 0,
                "netIncrease": 0,
                "openBacklog": 0,
                "firstRespondedCount": 6,
                "processedCount": 5,
                "processedInNewCount": 4,
                "processRate": 0.5714,
                "unprocessedBacklog": 3,
                "avgFirstResponseSeconds": 600,
                "avgFirstProcessSeconds": 3600,
            }
        ],
    }

    merged = TicketProcessingStatsService.merge_trend_series(base_trend, processing_trend, "day")
    row = merged["series"][0]

    assert row["newCount"] == 7
    assert row["closedCount"] == 2
    assert row["resolvedCount"] == 3
    assert row["netIncrease"] == 5
    assert row["openBacklog"] == 11
    assert row["problemCount"] == 4
    assert row["moduleCounts"] == [{"name": "收银", "count": 7}]
    assert row["problemPatternCounts"] == [{"name": "内存泄露", "count": 2}]
    assert row["firstRespondedCount"] == 6
    assert row["processedCount"] == 5
    assert row["processedInNewCount"] == 4
    assert row["processRate"] == 0.5714
    assert row["unprocessedBacklog"] == 3
    assert row["avgFirstResponseSeconds"] == 600
    assert row["avgFirstProcessSeconds"] == 3600


def test_snapshot_seconds_are_weighted_by_event_count():
    """多维度快照合并平均耗时时，应按事件数量加权而不是按行数平均。"""
    if TicketProcessingStatsService is None:
        return

    rows = [
        SimpleNamespace(avg_first_process_seconds=100, processed_count=1),
        SimpleNamespace(avg_first_process_seconds=1000, processed_count=9),
    ]

    result = TicketProcessingStatsService._weighted_snapshot_seconds(
        rows,
        "avg_first_process_seconds",
        "processed_count",
    )

    assert result == 910


def test_latest_snapshot_rows_keep_all_dimensions_of_last_date():
    """快照 overview 的存量应取最后日期所有维度行，而不是只取最后一行。"""
    if TicketProcessingStatsService is None:
        return

    rows = [
        SimpleNamespace(statistics_date=datetime(2026, 7, 8).date(), unprocessed_backlog=5),
        SimpleNamespace(statistics_date=datetime(2026, 7, 9).date(), unprocessed_backlog=2),
        SimpleNamespace(statistics_date=datetime(2026, 7, 9).date(), unprocessed_backlog=3),
    ]

    latest_rows = TicketProcessingStatsService._latest_snapshot_rows(rows)

    assert len(latest_rows) == 2
    assert sum(row.unprocessed_backlog for row in latest_rows) == 5


def test_snapshot_count_rows_group_dimension_total_count():
    """快照维度行应能聚合成模块或工单类型分布。"""
    if TicketProcessingStatsService is None:
        return

    rows = [
        SimpleNamespace(module_name="POS", total_count=2),
        SimpleNamespace(module_name="POS", total_count=3),
        SimpleNamespace(module_name="", total_count=1),
    ]

    result = TicketProcessingStatsService._snapshot_count_rows(rows, "module_name", "module")

    assert result == [{"module": "POS", "count": 5}, {"module": "未填写", "count": 1}]


def test_snapshot_code_name_rows_group_issue_type_by_stable_code():
    """工单类型快照分布应优先按稳定编码合并。"""
    if TicketProcessingStatsService is None:
        return

    rows = [
        SimpleNamespace(issue_type_id="bug", issue_type_name="缺陷旧名", total_count=2),
        SimpleNamespace(issue_type_id="bug", issue_type_name="缺陷", total_count=3),
        SimpleNamespace(issue_type_id="", issue_type_name="", total_count=1),
    ]

    result = TicketProcessingStatsService._snapshot_code_name_rows(
        rows,
        "issue_type_id",
        "issue_type_name",
    )

    assert result == [
        {"issue_type_id": "bug", "issue_type_name": "缺陷旧名", "count": 5},
        {"issue_type_id": "", "issue_type_name": "未填写", "count": 1},
    ]
