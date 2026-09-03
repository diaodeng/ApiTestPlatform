"""工单 AI 分析结果按 schema 清洗的回归测试。

背景：工单 INC00001920244（task_2046322511408128，prod 环境）AI 分析中，
deepseek-v4-flash（经 ai-router 中转，Provider shuidi）未被 codex
--output-schema 真实约束，输出了 schema 外字段（ticket_no、merchant_name、
version、root_cause_type），并把 evidence 写成 {source, content} 对象数组，
导致结果被丢弃（AI_WORKER_RESULT_INVALID）。同时该失败分支存在
invalid_result_token_usage 先使用后赋值的 UnboundLocalError，掩盖了真实失败原因。
"""

import json

from services.ticket_ai_result_schema_service import TicketAiResultSchemaService


def _build_schema() -> dict:
    """构造与服务端 _build_result_schema 一致的最小 schema。"""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ticket_id": {"type": ["integer", "string"]},
            "root_cause": {"type": "string"},
            "confidence": {"type": ["number", "string"]},
            "evidence": {"type": "array", "items": {"type": "string"}, "default": []},
            "needs_human_review": {"type": "boolean"},
        },
        "required": ["ticket_id", "root_cause", "evidence"],
    }


def test_sanitize_removes_extra_fields():
    """schema 外的额外字段应被剔除并记录清洗动作。"""
    schema = _build_schema()
    payload = {
        "ticket_id": "1",
        "root_cause": "r",
        "evidence": [],
        "ticket_no": "INC00001920244",
        "merchant_name": "MN(万宁)",
    }

    cleaned, actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert "ticket_no" not in cleaned
    assert "merchant_name" not in cleaned
    assert cleaned["root_cause"] == "r"
    assert any("ticket_no" in action for action in actions)


def test_sanitize_flattens_evidence_object_entries():
    """evidence 元素为 {source, content} 对象时应拼接为字符串。"""
    schema = _build_schema()
    payload = {
        "ticket_id": "1",
        "root_cause": "r",
        "evidence": [
            {"source": "logs/app.log:100", "content": "出现 NullPointerException"},
            {"source": "", "content": "只有内容的证据"},
            {"source": "只有来源"},
            "正常的字符串证据",
        ],
    }

    cleaned, actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert cleaned["evidence"][0] == "logs/app.log:100: 出现 NullPointerException"
    assert cleaned["evidence"][1] == "只有内容的证据"
    assert cleaned["evidence"][2] == "只有来源"
    assert cleaned["evidence"][3] == "正常的字符串证据"
    # 只有三条非字符串元素产生清洗动作
    assert len(actions) == 3


def test_sanitize_serializes_other_type_evidence_entries():
    """evidence 元素为数字/None 等其他类型时应 JSON 序列化保留信息。"""
    schema = _build_schema()
    payload = {"ticket_id": "1", "root_cause": "r", "evidence": [123, None]}

    cleaned, _actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert cleaned["evidence"][0] == "123"
    assert cleaned["evidence"][1] == "null"


def test_sanitize_keeps_valid_result_untouched():
    """已符合 schema 的结果不应产生任何清洗动作。"""
    schema = _build_schema()
    payload = {
        "ticket_id": "1",
        "root_cause": "r",
        "evidence": ["a", "b"],
        "needs_human_review": False,
    }

    cleaned, actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert actions == []
    assert cleaned == payload


def test_sanitize_ignores_evidence_rules_when_schema_requires_objects():
    """schema 自身要求 evidence 为对象时不应做归一化（清洗只服务当前字符串约定）。"""
    schema = _build_schema()
    schema["properties"]["evidence"] = {"type": "array", "items": {"type": "object"}}
    payload = {
        "ticket_id": "1",
        "root_cause": "r",
        "evidence": [{"source": "s", "content": "c"}],
    }

    cleaned, actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert cleaned["evidence"] == [{"source": "s", "content": "c"}]
    assert actions == []


def test_real_invalid_result_from_inc00001920244_passes_after_sanitize():
    """用真实失败任务的 result.json 结构验证清洗后可整体通过 schema 校验。"""
    schema = _build_schema()
    payload = {
        "ticket_id": "2046301603089408",
        "ticket_no": "INC00001920244",
        "project_id": "2015502723587072",
        "merchant_name": "MN(万宁)",
        "version_key": "wemn_vender_master_1.4.0.x",
        "version": "1.4.0.5",
        "repo_url": "git@gitlab.dmall.com:cpos-group/cpos-df.git",
        "branch_name": "wemn_vender_master_1.4.0.x",
        "root_cause_type": "code_defect",
        "root_cause": "POS 客户端 VMS 礼券核销缓存存在竞态缺陷。",
        "analysis_summary": "摘要",
        "related_files": ["interface/vms_voucher_interface.py"],
        "related_functions": ["redeem_params_cache"],
        "fix_suggestion": "修复建议",
        "confidence": 0.88,
        "evidence": [
            {"source": "原始日志:source_logs/2026-09-02_pos.log.23:9621-9629", "content": "核销返回 REDEEMED"},
            {"source": "原始日志:source_logs/2026-09-02_pos.log.24:1020-1040", "content": "创建 dataType=14 回滚任务"},
        ],
        "risk_items": ["偶发"],
        "next_steps": ["与 VMS 团队核实"],
    }

    cleaned, _actions = TicketAiResultSchemaService.sanitize_result_payload(payload, schema)

    assert "ticket_no" not in cleaned
    assert "root_cause_type" not in cleaned
    assert all(isinstance(item, str) for item in cleaned["evidence"])
    # required 字段在清洗后仍然齐全
    for field in schema["required"]:
        assert field in cleaned
    # 结果可被序列化回传
    json.dumps(cleaned, ensure_ascii=False)
