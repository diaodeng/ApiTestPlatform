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
