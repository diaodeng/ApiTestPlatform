"""未转义双引号 JSON 修复兜底的回归测试。

背景：工单 INC00001904725（task_2045268316707840，prod 环境）AI 分析中，
deepseek-v4-flash 模型在 root_cause 字符串值里输出了未转义英文双引号
（"停留在"恢复中"（Pending）状态"），导致 result.json 解析失败，
整个有效分析结果被丢弃（AI_WORKER_RESULT_UNPARSEABLE）。
"""

import json

from services.ticket_ai_analysis_service import TicketAiAnalysisService


def test_extract_json_repairs_unescaped_quote_inside_string_value():
    """字符串值内部的未转义引号（后跟中文/非结构字符）应被转义后正常解析。"""
    text = '```json\n{\n  "root_cause": "交易停留在"恢复中"（Pending）状态，非代码缺陷。",\n  "confidence": 0.9\n}\n```'

    payload = TicketAiAnalysisService._extract_json_from_text(text)

    assert payload is not None
    assert payload["root_cause"] == '交易停留在"恢复中"（Pending）状态，非代码缺陷。'
    assert payload["confidence"] == 0.9


def test_extract_json_repairs_quotes_from_plain_text_without_fence():
    """无代码块围栏的纯文本 JSON 也应走同样的修复兜底。"""
    text = '{"analysis_summary": "用户说"支付页返回后小票无明细"，经复核属实。"}'

    payload = TicketAiAnalysisService._extract_json_from_text(text)

    assert payload is not None
    assert payload["analysis_summary"] == '用户说"支付页返回后小票无明细"，经复核属实。'


def test_extract_json_keeps_normal_json_untouched():
    """合法 JSON（含已转义引号）不应被修复逻辑改写。"""
    text = json.dumps(
        {
            "root_cause": "引号\"已转义，行尾换行\n正常",
            "evidence": ["a", "b"],
        },
        ensure_ascii=False,
    )

    payload = TicketAiAnalysisService._extract_json_from_text(text)

    assert payload is not None
    assert payload["root_cause"] == '引号"已转义，行尾换行\n正常'
    assert payload["evidence"] == ["a", "b"]


def test_extract_json_does_not_break_real_close_quotes():
    """真实的键/值结束引号（后跟 , } ] :）不应被误转义。"""
    text = '{"a": "值一"，说明", "b": {"c": "值二"}, "d": ["e", "f"]}'

    payload = TicketAiAnalysisService._extract_json_from_text(text)

    assert payload is not None
    assert payload["a"] == '值一"，说明'
    assert payload["b"] == {"c": "值二"}
    assert payload["d"] == ["e", "f"]


def test_extract_json_returns_none_when_repair_cannot_fix():
    """无法修复的损坏文本应保持返回 None，不抛异常。"""
    text = '{"root_cause": "缺失结束引号， Broken'

    payload = TicketAiAnalysisService._extract_json_from_text(text)

    assert payload is None
