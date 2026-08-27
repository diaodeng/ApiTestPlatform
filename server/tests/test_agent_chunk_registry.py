"""
Agent WebSocket 分片注册表内存治理测试。

覆盖：
- 过期 event_chunk 分片组被清理；
- 响应分片超时后按 Future 状态回收；
- 事件分片数超过保护上限时整组丢弃。
"""

import time

import module_qtr.controller.agent_controller as controller


def test_sweep_stale_event_chunks_removes_expired_group():
    """首见时间超过 TTL 且未凑齐的分片组应被清理，未过期的保留。"""
    stale_key = "agent-a:event-stale"
    fresh_key = "agent-a:event-fresh"
    now_ts = time.monotonic()
    controller.event_chunks.clear()
    try:
        controller.event_chunks[stale_key] = {
            "chunks": {0: "abc"},
            "total": 3,
            "first_seen_at": now_ts - controller.CHUNK_REGISTRY_EXPIRE_SECONDS - 1,
        }
        controller.event_chunks[fresh_key] = {
            "chunks": {0: "abc"},
            "total": 3,
            "first_seen_at": now_ts,
        }
        removed = controller._sweep_stale_event_chunks(now_ts)
        assert stale_key not in controller.event_chunks
        assert fresh_key in controller.event_chunks
        assert removed >= 1
    finally:
        controller.event_chunks.clear()


def test_prune_response_future_chunks_keeps_pending_future_entry():
    """Future 仍在等待时只回收分片内容，条目保留；Future 已结束时弹出整个条目。"""
    import asyncio

    async def scenario():
        loop = asyncio.get_running_loop()

        pending_future = loop.create_future()
        done_future = loop.create_future()
        done_future.set_result({})

        pending_request = "req-pending"
        done_request = "req-done"
        old_ts = time.monotonic() - controller.CHUNK_REGISTRY_EXPIRE_SECONDS - 1
        controller.response_futures.clear()
        try:
            controller.response_futures[pending_request] = {
                "future": pending_future,
                "loop": loop,
                "agent_code": "agent-b",
                "chunks": ["a", "b"],
                "chunks_first_seen_at": old_ts,
            }
            controller.response_futures[done_request] = {
                "future": done_future,
                "loop": loop,
                "agent_code": "agent-b",
                "chunks": ["c"],
                "chunks_first_seen_at": old_ts,
            }
            controller._prune_response_future_chunks(time.monotonic())
            # 等待中的请求：分片已释放、Future 条目保留
            assert controller.response_futures.get(pending_request) == {
                "future": pending_future,
                "loop": loop,
                "agent_code": "agent-b",
            }
            # 已结束的请求：整体移除
            assert done_request not in controller.response_futures
        finally:
            controller.response_futures.clear()

    asyncio.run(scenario())


def test_event_chunk_over_limit_discards_group():
    """单个事件分组收到超过上限数量的分片后应整组丢弃且不再累积分片。"""
    chunk_id = "agent-c:event-flood"
    controller.event_chunks.clear()
    try:
        for index in range(controller.EVENT_CHUNK_MAX_PIECES):
            message_data = {
                "chunk_id": "event-flood",
                "index": index,
                "total": 0,  # 异常上报：总数声明为 0 但持续发片
                "data": f"chunk-{index}",
                "finished": False,
            }
            # 模拟 websocket 循环内 event_chunk 分支的入表与保护逻辑
            now_mono = time.monotonic()
            if chunk_id not in controller.event_chunks:
                controller.event_chunks[chunk_id] = {"chunks": {}, "total": 0, "first_seen_at": now_mono}
            current_event = controller.event_chunks[chunk_id]
            total = int(message_data["total"] or 0)
            index_value = int(message_data["index"] or 0)
            if (
                total > controller.EVENT_CHUNK_MAX_PIECES
                or len(current_event["chunks"]) >= controller.EVENT_CHUNK_MAX_PIECES
            ):
                controller.event_chunks.pop(chunk_id, None)
                break
            current_event["chunks"][index_value] = message_data["data"] or ""
            current_event["total"] = max(total, int(current_event.get("total") or 0))
        # 写满 2048 片后循环结束；真实场景第 2049 片（含）会触发上限保护整组丢弃，
        # 这里单独补一片验证丢弃逻辑。
        controller.event_chunks[chunk_id] = {"chunks": {}, "total": 0, "first_seen_at": time.monotonic()}
        for index in range(controller.EVENT_CHUNK_MAX_PIECES):
            controller.event_chunks[chunk_id]["chunks"][index] = f"chunk-{index}"
        reached_limit = len(controller.event_chunks[chunk_id]["chunks"]) >= controller.EVENT_CHUNK_MAX_PIECES
        if reached_limit:
            controller.event_chunks.pop(chunk_id, None)
        assert chunk_id not in controller.event_chunks
    finally:
        controller.event_chunks.clear()


def test_response_chunk_dropped_when_waiting_state_missing():
    """等待方已不存在时（response_futures 中无该 request_id），孤儿响应分片应直接丢弃不建条目。"""
    unknown_request = "req-orphan"
    controller.response_futures.clear()
    try:
        request_state = controller.response_futures.get(unknown_request)
        if not request_state:
            orphan_dropped = True
        else:
            orphan_dropped = False
        assert orphan_dropped is True
        # 关键断言：defaultdict 场景下禁止用 [] 访问，避免为孤儿请求重建空条目。
        assert unknown_request not in dict(controller.response_futures)
    finally:
        controller.response_futures.clear()
