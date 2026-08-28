from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.core.ticket_service import TicketService
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from modules.ticket.service.export.ticket_export_service import TicketExportService
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
