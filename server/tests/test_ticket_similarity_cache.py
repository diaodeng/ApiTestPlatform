from types import SimpleNamespace
from unittest.mock import Mock

from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.ai import ticket_similar_result_cache_service as cache_module
from modules.ticket.service.ai.ticket_hybrid_similarity_service import TicketHybridSimilarityService
from modules.ticket.service.ai.ticket_similar_result_cache_service import TicketSimilarResultCacheService
from modules.ticket.service.core.ticket_read_service import TicketReadService


def _make_ticket(ticket_id: int) -> Ticket:
    """构造最小可用的工单实体。"""
    return SimpleNamespace(
        ticket_id=ticket_id,
        ticket_no=f"T-{ticket_id}",
        title="支付接口超时",
        description="下单接口超时",
        project_id=10,
        module_id=20,
        affected_version_id=30,
    )


def test_signal_loop_collects_all_signal_types(monkeypatch):
    """精确信号候选应收集全部信号类型的命中，而不是只剩最后一种。"""
    source = _make_ticket(1)
    calls: list[tuple[str, list[str]]] = []

    def fake_list_signals(db, signal_type, signal_values):
        calls.append((signal_type, list(signal_values)))
        return {}

    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketDao.list_ticket_ids_by_similarity_signals",
        fake_list_signals,
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketSimilarityProfileService.get_metadata",
        lambda db, ticket: {"signals": {"trace_id": ["trace-1"], "request_id": ["req-1"], "error_code": ["E1"]}},
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketEmbeddingService.search_embedding_records_by_vector",
        lambda db, vector, limit, config, provider, embedding_scope="symptom": {},
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketDao.get_tickets_by_ids",
        lambda db, ids: [],
    )
    TicketHybridSimilarityService.search_by_vector(
        Mock(), source, [0.1, 0.2], 5, {"vectorWeight": 0.85, "keywordWeight": 0.15}, embedding_scopes=("symptom",)
    )
    # 三种信号类型都被查询过
    queried_types = [item[0] for item in calls]
    assert queried_types == ["trace_id", "request_id", "error_code"]


def test_signal_loop_passes_all_signal_candidates_to_fetch(monkeypatch):
    """修复后，三类信号命中的候选都应传入候选工单批量查询。"""
    source = _make_ticket(1)
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketDao.list_ticket_ids_by_similarity_signals",
        # 每类信号固定返回一个唯一候选工单：trace_id→101, request_id→102, error_code→103
        lambda db, signal_type, values: {{"trace_id": 101, "request_id": 102, "error_code": 103}[signal_type]: set(values)}
        if values
        else {},
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketSimilarityProfileService.get_metadata",
        lambda db, ticket: {"signals": {"trace_id": ["t1"], "request_id": ["r1"], "error_code": ["e1"]}},
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketEmbeddingService.search_embedding_records_by_vector",
        lambda db, vector, limit, config, provider, embedding_scope="symptom": {},
    )
    captured_ids: list[list[int]] = []

    def fake_get_tickets(db, ids):
        captured_ids.append(list(ids))
        return []

    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_hybrid_similarity_service.TicketDao.get_tickets_by_ids",
        fake_get_tickets,
    )
    TicketHybridSimilarityService.search_by_vector(
        Mock(), source, [0.1], 5, {}, embedding_scopes=("symptom",)
    )
    assert captured_ids, "应至少调用一次候选批量查询"
    final_ids = set(captured_ids[-1])
    # 三类信号各自返回一个固定候选（101/102/103），修复后都应进入最终候选集
    assert {101, 102, 103} <= final_ids


def test_cache_memory_backend_roundtrip_and_invalidate(monkeypatch):
    """memory 后端下缓存读写与按工单失效应正确工作。"""
    monkeypatch.setattr(cache_module.RedisConfig, "cache_backend", "memory")
    cache_module.TicketSimilarResultCacheService._memory_store.clear()

    key = TicketSimilarResultCacheService.build_key(123, 5, "fp1")
    payload = {"status": "ready", "items": [{"ticketId": "9"}]}
    TicketSimilarResultCacheService.set(key, payload)
    assert TicketSimilarResultCacheService.get(key) == payload
    # 不同工单/limit/指纹互不影响
    assert TicketSimilarResultCacheService.get(TicketSimilarResultCacheService.build_key(124, 5, "fp1")) is None
    assert TicketSimilarResultCacheService.get(TicketSimilarResultCacheService.build_key(123, 10, "fp1")) is None
    # 失效后读不到
    assert TicketSimilarResultCacheService.invalidate_ticket(123) >= 1
    assert TicketSimilarResultCacheService.get(key) is None


def test_cache_memory_backend_expires(monkeypatch):
    """memory 后端过期条目应视为未命中。"""
    monkeypatch.setattr(cache_module.RedisConfig, "cache_backend", "memory")
    cache_module.TicketSimilarResultCacheService._memory_store.clear()

    key = TicketSimilarResultCacheService.build_key(200, 5, "fp2")
    TicketSimilarResultCacheService.set(key, {"status": "ready", "items": []})
    # 手动把过期时间拨到过去
    expires_at, payload = cache_module.TicketSimilarResultCacheService._memory_store[key]
    cache_module.TicketSimilarResultCacheService._memory_store[key] = (expires_at - 1000, payload)
    assert TicketSimilarResultCacheService.get(key) is None


def test_get_similar_tickets_uses_cache_before_full_query(monkeypatch):
    """缓存命中时不应触发完整相似查询链路。"""
    monkeypatch.setattr(cache_module.RedisConfig, "cache_backend", "memory")
    cache_module.TicketSimilarResultCacheService._memory_store.clear()

    ticket = SimpleNamespace(ticket_id=7)
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.get_ticket_by_id",
        lambda db, tid: ticket,
    )
    cached_payload = {
        "status": "ready",
        "message": "",
        "items": [{"ticketId": "8", "score": 0.9}],
        "symptomTickets": [{"ticketId": "8", "score": 0.9}],
        "caseTickets": [],
    }
    key = TicketSimilarResultCacheService.build_key(7, 5, "default")
    TicketSimilarResultCacheService.set(key, cached_payload)

    full_query_called = False

    def fake_full_query(db, tid, limit):
        nonlocal full_query_called
        full_query_called = True
        return {"similarTickets": [], "symptomTickets": [], "caseTickets": [], "similarEmbeddingStatus": "ready"}

    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketSimilarityQueryService.search_similar_tickets_by_ticket",
        fake_full_query,
    )

    result = TicketReadService.get_similar_tickets(Mock(), 7, 5)
    assert full_query_called is False
    assert result is not None
    assert result.status == "ready"
    assert [item.ticket_id for item in result.items] == ["8"]


def test_get_similar_tickets_skips_cache_on_error_result(monkeypatch):
    """查询状态为 error 的结果不应写入缓存，下次查询仍走完整链路。"""
    monkeypatch.setattr(cache_module.RedisConfig, "cache_backend", "memory")
    cache_module.TicketSimilarResultCacheService._memory_store.clear()

    ticket = SimpleNamespace(ticket_id=9)
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketDao.get_ticket_by_id",
        lambda db, tid: ticket,
    )
    monkeypatch.setattr(
        "modules.ticket.service.core.ticket_read_service.TicketSimilarityQueryService.search_similar_tickets_by_ticket",
        lambda db, tid, limit: {
            "similarTickets": [],
            "symptomTickets": [],
            "caseTickets": [],
            "similarEmbeddingStatus": "error",
            "similarEmbeddingMessage": "相似工单查询失败：boom",
        },
    )
    result = TicketReadService.get_similar_tickets(Mock(), 9, 5)
    assert result.status == "error"
    # 缓存中不应有条目
    assert cache_module.TicketSimilarResultCacheService._memory_store == {}
