from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.service.export.ticket_export_service import (
    ISSUE_TICKET_EXPORT_COLUMNS,
    TICKET_EXPORT_COLUMNS,
    TicketExportService,
)
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.util.ticket_excel_export_util import MAX_EXPORT_ROWS


def test_export_selected_tickets_uses_ticket_query_aliases(monkeypatch):
    """选中工单导出必须把 ID 与分页参数传入 TicketQueryModel。"""
    captured_queries = []

    monkeypatch.setattr(
        TicketService,
        "_build_ticket_list_filter_query",
        staticmethod(lambda _query_db, query: query),
    )
    monkeypatch.setattr(
        TicketDao,
        "get_ticket_list",
        staticmethod(lambda _query_db, query: captured_queries.append(query) or []),
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "get_latest_summary_map",
        staticmethod(lambda _query_db, _ticket_ids: {}),
    )
    monkeypatch.setattr(
        TicketAiAnalysisService,
        "get_latest_summary_map",
        staticmethod(lambda _query_db, _ticket_ids: {}),
    )
    monkeypatch.setattr(
        TicketVersionService,
        "attach_ticket_version_labels",
        staticmethod(lambda _query_db, _rows: None),
    )
    monkeypatch.setattr(
        TicketService,
        "_attach_issue_summary",
        staticmethod(lambda _query_db, _rows: None),
    )

    TicketExportService._export_tickets_by_ids(object(), [9876543210123])

    assert len(captured_queries) == 1
    query = captured_queries[0]
    assert query.ticket_ids == "9876543210123"
    assert query.page_num == 1
    assert query.page_size == MAX_EXPORT_ROWS + 1
    assert query.is_page is True


def test_ticket_url_export_column_defined():
    """工单导出与问题实例导出列定义都必须包含 URL 列。"""
    assert any(col.key == "ticketUrl" and col.label == "URL" for col in TICKET_EXPORT_COLUMNS)
    assert any(col.key == "ticketUrl" and col.label == "URL" for col in ISSUE_TICKET_EXPORT_COLUMNS)


def test_format_ticket_field_ticket_url():
    """ticketUrl 导出字段取装饰后的 camelCase 值，空值输出空字符串而非 '-' 或 None。"""
    row = {"ticketUrl": "https://ticket.example.com/detail/123"}
    assert TicketExportService._format_ticket_field(None, "ticketUrl", row, 1) == (
        "https://ticket.example.com/detail/123"
    )
    # snake_case 兜底
    assert TicketExportService._format_ticket_field(None, "ticketUrl", {"ticket_url": "https://a.b/c"}, 1) == (
        "https://a.b/c"
    )
    # 空值兜底为空字符串
    assert TicketExportService._format_ticket_field(None, "ticketUrl", {}, 1) == ""
    assert TicketExportService._format_ticket_field(None, "ticketUrl", {"ticketUrl": None}, 1) == ""
