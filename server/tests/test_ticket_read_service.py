from types import SimpleNamespace
from unittest.mock import Mock

from modules.ticket.entity.vo.ticket_read_vo import (
    TicketMessagesPageQueryModel,
    TicketSimilarQueryModel,
    TicketSnapshotsPageQueryModel,
)
from modules.ticket.service.core.ticket_read_service import TicketReadService


def test_read_limit_query_normalizes_default_and_upper_bound():
    """只读查询数量应使用各接口默认值，并统一限制在 1 到 100。"""
    assert TicketSimilarQueryModel().limit == 5
    assert TicketMessagesPageQueryModel().limit == 20
    assert TicketSnapshotsPageQueryModel(limit=999).limit == 100
    assert TicketSnapshotsPageQueryModel(limit=0).limit == 1


def test_similar_item_uses_summary_whitelist_and_string_id():
    """相似工单投影应仅保留白名单字段，且不泄漏描述和扩展字段。"""
    item = TicketReadService._project_similar_item(
        {
            "ticketId": 9007199254740993,
            "ticketNo": "T-100",
            "title": "支付异常",
            "status": "resolved",
            "description": "不应返回的完整描述",
            "extraData": {"secret": "不应返回"},
            "score": 0.87654,
        }
    )

    payload = item.model_dump(by_alias=True)
    assert payload["ticketId"] == "9007199254740993"
    assert payload["ticketNo"] == "T-100"
    assert payload["score"] == 0.87654
    assert "description" not in payload
    assert "extraData" not in payload


def test_messages_page_returns_latest_limit_and_has_more(monkeypatch):
    """消息按需接口应返回最近数量，并正确标记是否还有更早记录。"""
    ticket = SimpleNamespace(ticket_id=1)
    rows = [SimpleNamespace(id=index, ticket_id=1, role="user", content=f"m-{index}") for index in range(1, 5)]
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.get_ticket_by_id",
        lambda db, tid: ticket,
    )
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.list_messages",
        lambda db, tid, limit: rows[-limit:],
    )

    result = TicketReadService.get_messages_page(Mock(), 1, 2)

    assert result is not None
    assert [item.id for item in result.items] == ["3", "4"]
    assert result.has_more is True


def test_snapshots_page_keeps_latest_first(monkeypatch):
    """快照按需接口应保持最新版本优先。"""
    ticket = SimpleNamespace(ticket_id=1)
    rows = [
        SimpleNamespace(id=index, ticket_id=1, version=version, summary=f"s-{version}")
        for index, version in ((4, 4), (3, 3), (2, 2), (1, 1))
    ]
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.get_ticket_by_id",
        lambda db, tid: ticket,
    )
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.list_snapshots",
        lambda db, tid, limit: rows[: limit + 1],
    )

    result = TicketReadService.get_snapshots_page(Mock(), 1, 2)

    assert result is not None
    assert [item.version for item in result.items] == [4, 3]
    assert result.has_more is True
