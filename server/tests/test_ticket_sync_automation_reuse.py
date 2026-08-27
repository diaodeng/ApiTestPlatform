from types import SimpleNamespace

from modules.ticket.dao.ticket_dao import TicketDao
from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service import TicketAutoAiAnalysisConditionService
from modules.ticket.service.ai.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.sync.ticket_sync_automation_input_service import TicketSyncAutomationInputService
from modules.ticket.service.sync.ticket_sync_automation_service import TicketSyncAutomationService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_payload_service import TicketSyncPayloadService


class DummyDb:
    """模拟同步自动化所需的最小数据库会话。"""

    def __init__(self):
        self.flush_count = 0
        self.commit_count = 0

    def flush(self):
        """记录 flush 调用次数。"""
        self.flush_count += 1

    def commit(self):
        """记录 commit 调用次数。"""
        self.commit_count += 1


def _build_ticket():
    """构造自动化测试使用的最小工单对象。"""
    return SimpleNamespace(
        ticket_id=1001,
        ticket_no="INC-1001",
        title="工单标题",
        description="工单描述",
        merchant_name="",
        module_name="",
        root_cause="",
        solution="",
        project_id=None,
        module_id=None,
        module_code="",
        status="处理中",
        affected_version_id=None,
        extra_data={},
    )


def _build_current_user():
    """构造最小登录用户对象。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester", nick_name="tester"))


def _patch_common_dependencies(monkeypatch, ticket):
    """为同步自动化测试统一打桩公共依赖。"""
    monkeypatch.setattr(TicketDao, "get_ticket_by_id", lambda db, ticket_id: ticket)
    monkeypatch.setattr(TicketDao, "update_ticket", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        TicketSyncConfigService,
        "load_sync_config",
        lambda db: {"automationNotification": {}, "logPullDefaults": {}},
    )
    monkeypatch.setattr(TicketSyncPayloadService, "build_meta", lambda extra_data: {})
    monkeypatch.setattr(TicketSyncPayloadService, "attach_meta", lambda extra_data, meta: extra_data)
    monkeypatch.setattr(TicketEmbeddingService, "search_tickets", lambda *args, **kwargs: [])
    monkeypatch.setattr(TicketSyncAutomationService, "collect_text", lambda payload: "ticket-context")


def test_run_sync_automation_reuses_matching_success_log_record(monkeypatch):
    """自动拉日志命中相同成功参数时，应跳过重复拉取并复用已有记录。"""
    db = DummyDb()
    ticket = _build_ticket()
    sync_object = SimpleNamespace(
        ticket_no="INC-REUSE",
        automation=SimpleNamespace(
            auto_log_pull=True,
            auto_ai_analysis=True,
            ai_agent_code="agent-prod",
            ai_provider_code="provider-prod",
            extra_instruction="",
        ),
    )
    existing_record = SimpleNamespace(id=2043149749595136, status="success", status_desc="拉取成功")
    steps: list[dict] = []

    _patch_common_dependencies(monkeypatch, ticket)
    monkeypatch.setattr(
        TicketSyncAutomationInputService,
        "resolve_runtime_config",
        lambda **kwargs: {
            "environment": "prod",
            "vendorId": 11,
            "storeId": "552283",
            "posNo": 2,
            "commandDataType": 1,
            "modifyTime": "2026-08-20",
        },
    )
    monkeypatch.setattr(TicketSyncAutomationInputService, "resolve_modify_time", lambda **kwargs: "2026-08-20")
    monkeypatch.setattr(TicketLogPullDao, "verify_store_by_org_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        TicketSyncAutomationService,
        "mark_automation_step",
        lambda meta, **kwargs: steps.append(kwargs) or meta,
    )
    monkeypatch.setattr(TicketLogPullService, "find_matching_success_record", lambda *args, **kwargs: existing_record)
    monkeypatch.setattr(
        TicketLogPullService,
        "trigger_auto_ai_analysis",
        lambda *args, **kwargs: {"status": "submitted", "recordId": str(existing_record.id), "taskId": "301"},
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "create_log_pull_services",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("命中重复成功记录后不应再次创建日志拉取任务")),
    )

    result = TicketSyncAutomationService.run_sync_automation(
        db,
        ticket_id=1001,
        sync_object=sync_object,
        detected={},
        current_user=_build_current_user(),
    )

    assert result["logPull"]["reused"] is True
    assert result["logPull"]["recordId"] == str(existing_record.id)
    assert result["aiAnalysis"]["taskId"] == "301"
    assert any(item["step"] == "log_pull" and item["status"] == "skipped" for item in steps)
    assert any(item["step"] == "ai_analysis" and item["status"] == "submitted" for item in steps)


def test_run_sync_automation_reuses_latest_success_log_for_auto_ai_only(monkeypatch):
    """仅开启自动 AI 时，应直接复用最近成功日志记录继续分析。"""
    db = DummyDb()
    ticket = _build_ticket()
    sync_object = SimpleNamespace(
        ticket_no="INC-AI-ONLY",
        automation=SimpleNamespace(
            auto_log_pull=False,
            auto_ai_analysis=True,
            ai_agent_code="agent-prod",
            ai_provider_code="provider-prod",
            extra_instruction="",
        ),
    )
    existing_record = SimpleNamespace(id=2043149749595137, status="success", status_desc="拉取成功")
    steps: list[dict] = []

    _patch_common_dependencies(monkeypatch, ticket)
    monkeypatch.setattr(
        TicketSyncAutomationService,
        "mark_automation_step",
        lambda meta, **kwargs: steps.append(kwargs) or meta,
    )
    monkeypatch.setattr(TicketAutoAiAnalysisConditionService, "check_conditions", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        TicketLogPullDao,
        "get_latest_success_record_by_ticket_id",
        lambda *args, **kwargs: existing_record,
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "trigger_auto_ai_analysis",
        lambda *args, **kwargs: {"status": "submitted", "recordId": str(existing_record.id), "taskId": "302"},
    )

    result = TicketSyncAutomationService.run_sync_automation(
        db,
        ticket_id=1001,
        sync_object=sync_object,
        detected={},
        current_user=_build_current_user(),
    )

    assert result["aiAnalysis"]["recordId"] == str(existing_record.id)
    assert result["aiAnalysis"]["taskId"] == "302"
    assert any(item["step"] == "ai_analysis" and item["status"] == "submitted" for item in steps)
