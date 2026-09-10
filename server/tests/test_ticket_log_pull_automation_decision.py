"""自动化日志拉取同参数决策矩阵测试。

覆盖 ticket_log_pull_automation_decision_service.decide 的分支：
- 无同参数记录 → create
- 同参数记录进行中 → wait，且场景要求 AI 时合并快照
- 同参数最新记录成功 → reuse，按记录级 AI 任务决定 analyze_existing
- 同参数最新记录失败/异常 → skip_failed
- 同参数记录已取消 → create（允许重建）
"""

from __future__ import annotations

from types import SimpleNamespace

from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.service.log_pull.ticket_log_pull_automation_decision_service import (
    TicketLogPullAutomationDecisionService,
)
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService


class DummyDb:
    """模拟决策服务所需的最小数据库会话。"""

    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0

    def commit(self):
        """记录 commit 次数。"""
        self.commit_count += 1

    def rollback(self):
        """记录 rollback 次数。"""
        self.rollback_count += 1

    def add(self, obj):
        """模拟会话 add。"""

    def query(self, *args, **kwargs):
        """决策矩阵主链路不应触发 ORM 查询（由 DAO stub 顶替）。"""
        raise AssertionError("决策矩阵不应直接使用 db.query")


def _build_payload() -> TicketLogPullCreateModel:
    """构造标准拉取参数模型。"""
    return TicketLogPullCreateModel.model_validate(
        {
            "environment": "prod",
            "vendorId": 11,
            "storeId": "552283",
            "posNo": 2,
            "commandDataType": 1,
            "modifyTime": "2026-08-20",
        }
    )


def _build_record(record_id: int, status: str, command_content: dict | None = None):
    """构造最小拉取记录对象。"""
    return SimpleNamespace(
        id=record_id,
        ticket_id=1001,
        status=status,
        status_desc=status,
        error_message=None,
        command_content=command_content if command_content is not None else {},
        create_time=None,
    )


def _stub_records(monkeypatch, records: list):
    """打桩 DAO 最近记录查询与签名比对，直接返回同参数记录列表。"""
    monkeypatch.setattr(
        TicketLogPullDao,
        "list_recent_records_by_pull_identity",
        lambda db, **kwargs: records,
    )
    # 签名比对使用真实实现，但为避免依赖 payload 时间解析差异，统一桩为 True
    monkeypatch.setattr(
        TicketLogPullService,
        "_build_pull_identity_from_record",
        lambda record: "same",
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "_build_pull_identity_from_payload",
        lambda payload: "same",
    )


def test_decide_creates_when_no_matching_record(monkeypatch):
    """无同参数记录时应允许创建新拉取。"""
    _stub_records(monkeypatch, [])
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "create"


def test_decide_waits_for_active_record_and_merges_ai_config(monkeypatch):
    """同参数记录进行中应等待，且场景要求 AI 时向快照补充缺失的自动AI配置。"""
    record = _build_record(100, "polling")
    _stub_records(monkeypatch, [record])
    merged: dict = {}

    def fake_update(db, record_id, data):
        merged["record_id"] = record_id
        merged["command_content"] = data["command_content"]

    monkeypatch.setattr(TicketLogPullDao, "update_record", fake_update)

    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "wait"
    assert decision.record_id == 100
    assert merged["record_id"] == 100
    assert merged["command_content"]["_automation"]["autoAiEnabled"] is True


def test_decide_wait_does_not_override_existing_ai_flag(monkeypatch):
    """进行中记录快照已开启自动AI时不应重复写入。"""
    record = _build_record(101, "downloading", {"_automation": {"autoAiEnabled": True}})
    _stub_records(monkeypatch, [record])
    monkeypatch.setattr(
        TicketLogPullDao,
        "update_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("已有autoAiEnabled时不应再写快照")),
    )
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "wait"


def test_decide_reuses_success_record_without_ai_task(monkeypatch):
    """同参数成功记录且无 AI 任务时应复用并要求分析。"""
    record = _build_record(102, "success")
    _stub_records(monkeypatch, [record])
    monkeypatch.setattr(
        "modules.ticket.dao.ticket_ai_dao.TicketAiDao.get_latest_task_by_log_pull_record_id",
        lambda db, record_id: None,
    )
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "reuse"
    assert decision.record_id == 102
    assert decision.analyze_existing is True


def test_decide_reuse_skips_when_record_already_analyzed(monkeypatch):
    """成功记录已有成功 AI 任务时应复用但跳过重复分析。"""
    record = _build_record(103, "success")
    _stub_records(monkeypatch, [record])
    monkeypatch.setattr(
        "modules.ticket.dao.ticket_ai_dao.TicketAiDao.get_latest_task_by_log_pull_record_id",
        lambda db, record_id: SimpleNamespace(task_id=9001, status="success"),
    )
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "reuse"
    assert decision.analyze_existing is False


def test_decide_skips_failed_record_silently(monkeypatch):
    """同参数最新记录失败时应静默跳过（不创建、不AI、不通知）。"""
    record = _build_record(104, "failed")
    record.error_message = "外部平台返回失败"
    _stub_records(monkeypatch, [record])
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "skip_failed"
    assert decision.record_id == 104


def test_decide_allows_recreate_after_cancelled(monkeypatch):
    """同参数记录被人工停止（cancelled）后应允许重新创建。"""
    record = _build_record(105, "cancelled")
    _stub_records(monkeypatch, [record])
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "create"


def test_decide_uses_latest_matching_record(monkeypatch):
    """应取签名匹配的最新一条记录决策（新记录在前，旧失败记录在后）。"""
    latest_success = _build_record(106, "success")
    older_failed = _build_record(107, "failed")
    _stub_records(monkeypatch, [latest_success, older_failed])
    monkeypatch.setattr(
        "modules.ticket.dao.ticket_ai_dao.TicketAiDao.get_latest_task_by_log_pull_record_id",
        lambda db, record_id: SimpleNamespace(task_id=9002, status="success"),
    )
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=False
    )
    assert decision.action == "reuse"
    assert decision.record_id == 106


def test_decide_ignores_signature_mismatch_records(monkeypatch):
    """同工单但参数签名不一致的记录不参与决策。"""
    record = _build_record(108, "failed")
    _stub_records(monkeypatch, [record])
    monkeypatch.setattr(
        TicketLogPullService,
        "_build_pull_identity_from_record",
        lambda record: "different",
    )
    decision = TicketLogPullAutomationDecisionService.decide(
        DummyDb(), 1001, _build_payload(), auto_ai_enabled=True
    )
    assert decision.action == "create"
