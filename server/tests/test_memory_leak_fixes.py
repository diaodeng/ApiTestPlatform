"""
内存治理相关工具测试：
- IP 归属地缓存的过期清理与容量上限；
- 工单 AI 审计载荷/文本的超长裁剪。
"""

# 先通过完整入口链路完成模块初始化，规避 log_annotation 与登录服务的循环导入
import common.permission.sync  # noqa: F401
from module_admin.annotation.log_annotation import (
    IP_LOCATION_CACHE_MAX_ENTRIES,
    _ip_location_cache,
    _prune_ip_location_cache,
)
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


def test_ip_location_cache_prunes_expired_entries():
    """过期条目在写入后应被清理，未过期条目保留。"""
    now = 1000.0
    try:
        _ip_location_cache.clear()
        _ip_location_cache["1.1.1.1"] = (now - 1, "已过期")
        _ip_location_cache["2.2.2.2"] = (now + 3600, "有效")
        _prune_ip_location_cache(now)
        assert "1.1.1.1" not in _ip_location_cache
        assert "2.2.2.2" in _ip_location_cache
    finally:
        _ip_location_cache.clear()


def test_ip_location_cache_enforces_capacity_limit():
    """超过容量上限时应按过期时间淘汰最旧条目。"""
    now = 1000.0
    try:
        _ip_location_cache.clear()
        # 写满上限 + 10 个未过期条目，最旧的 10 个应被淘汰
        for index in range(IP_LOCATION_CACHE_MAX_ENTRIES + 10):
            _ip_location_cache[f"10.0.0.{index}"] = (now + index, f"区域{index}")
        _prune_ip_location_cache(now + IP_LOCATION_CACHE_MAX_ENTRIES + 5)
        assert len(_ip_location_cache) <= IP_LOCATION_CACHE_MAX_ENTRIES
        # 最小的（最先写入的）应被淘汰
        assert "10.0.0.0" not in _ip_location_cache
    finally:
        _ip_location_cache.clear()


def test_execution_payload_compaction_truncates_large_strings():
    """审计载荷中的超长字符串字段应被替换为截断占位文本。"""
    long_log_text = "L" * 100000
    payload = {
        "taskId": 123,
        "context": {"sourceLogPull": {"text": long_log_text}, "logAnalysisMode": "digest"},
        "timeline": [{"content": f"row-{index}"} for index in range(300)],
    }
    compacted = TicketAiAnalysisService._compact_execution_payload(payload)
    # 大文本被截断
    truncated_field = compacted["context"]["sourceLogPull"]["text"]
    assert len(truncated_field) < 2000
    assert "审计载荷长文本已截断" in truncated_field
    # 小字段原样保留
    assert compacted["taskId"] == 123
    assert compacted["context"]["logAnalysisMode"] == "digest"
    # 超长列表被裁剪到上限
    assert len(compacted["timeline"]) <= 200


def test_execution_text_truncation():
    """响应文本超长时保留头部并附加说明；空白文本返回 None。"""
    long_output = "E" * 50000
    truncated = TicketAiAnalysisService._truncate_execution_text(long_output)
    assert truncated is not None
    assert truncated.startswith("EEEE")
    assert "审计文本超长已截断" in truncated

    assert TicketAiAnalysisService._truncate_execution_text("   ") is None
    assert TicketAiAnalysisService._truncate_execution_text(None) is None
