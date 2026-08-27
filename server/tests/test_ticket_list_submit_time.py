from datetime import datetime

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketAiAnalysisTask
from modules.ticket.entity.do.ticket_log_pull_do import TicketLogPullRecord
from modules.ticket.entity.vo.ticket_vo import TicketQueryModel
from modules.ticket.service.core.ticket_service import TicketService
from utils.page_util import PageUtil


def _index_columns(model) -> dict[str, list[str]]:
    """返回模型索引名称及列顺序，验证 ORM 元数据与手工 DDL 一致。"""
    return {index.name: [column.name for column in index.columns] for index in model.__table__.indexes}


def test_ticket_list_query_uses_submit_time_without_json_fallback(monkeypatch):
    """工单列表提交时间筛选和排序只能使用主表 submit_time。"""
    captured_query = None

    def capture_paginate(query, page_num, page_size, is_page):
        nonlocal captured_query
        captured_query = query
        return query

    monkeypatch.setattr(PageUtil, "paginate", staticmethod(capture_paginate))
    session = Session()
    try:
        TicketDao.get_ticket_list(
            session,
            TicketQueryModel(
                submit_begin_time=datetime(2026, 8, 1),
                submit_end_time=datetime(2026, 8, 31, 23, 59, 59),
                sort_field="submitTime",
                sort_order="desc",
            ),
        )
    finally:
        session.close()

    sql = str(captured_query.statement.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "ticket.submit_time" in sql
    assert "JSON_EXTRACT" not in sql
    assert "externalCreateTime" not in sql
    assert "coalesce(ticket.submit_time" not in sql.lower()


def test_ticket_response_decoration_does_not_backfill_submit_time_from_sync_metadata():
    """工单响应不能将同步 JSON 时间或创建时间伪装为业务提交时间。"""
    item = {
        "createTime": "2026-08-01 10:00:00",
        "extraData": {"external_sync": {"externalCreateTime": "2026-07-31T10:00:00"}},
    }

    TicketService._decorate_ticket_item(item)

    assert item.get("submitTime") is None
    assert item["externalCreateTime"] == "2026-07-31T10:00:00"


def test_ticket_submit_time_performance_indexes_match_manual_ddl():
    """ORM 索引元数据必须与生产手工执行的性能索引完全一致。"""
    assert _index_columns(Ticket)["idx_ticket_del_module_code_submit_time"] == [
        "del_flag",
        "module_code",
        "submit_time",
        "ticket_id",
    ]
    assert _index_columns(TicketLogPullRecord)["idx_ticket_log_pull_ticket_created_status"] == [
        "ticket_id",
        "create_time",
        "id",
        "status",
    ]
    assert _index_columns(TicketAiAnalysisTask)["idx_ticket_ai_task_ticket_created_status"] == [
        "ticket_id",
        "create_time",
        "task_id",
        "status",
    ]
