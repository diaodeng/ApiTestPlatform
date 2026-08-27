from datetime import datetime
from types import SimpleNamespace

import pytest

from modules.ticket.dao.ticket_log_pull_dao import TicketLogPullDao
from modules.ticket.entity.vo.ticket_log_pull_vo import TicketLogPullCreateModel
from modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service import TicketAutoAiAnalysisConditionService
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService


class DummyUser:
    """仅用于通过类型参数传递的简化用户对象。"""

    user = SimpleNamespace(user_name="tester", user_id=7)


def test_get_external_config_services_returns_grouped_environments(monkeypatch):
    """外部环境列表接口应返回归一化后的分组配置。"""
    monkeypatch.setattr(TicketLogPullService, "ensure_param_config_rows", lambda db: None)
    monkeypatch.setattr(
        TicketLogPullDao,
        "get_external_config_row",
        lambda db: SimpleNamespace(
            config_value='{"dev": {"baseUrl": "https://dev.example.com"}, "prod": {"baseUrl": "https://prod.example.com"}}'
        ),
    )

    result = TicketLogPullService.get_external_config_services(object())

    assert result["groups"]["dev"]["defaultItem"] == "dev"
    assert result["groups"]["dev"]["items"]["dev"]["baseUrl"] == "https://dev.example.com"
    assert result["groups"]["prod"]["items"]["prod"]["baseUrl"] == "https://prod.example.com"


def test_retry_log_pull_services_rejects_missing_environment(monkeypatch):
    """旧记录没有保存 environment 时，重新拉取应直接失败并给出明确提示。"""
    record = SimpleNamespace(id=2011730395835392, ticket_id=1001, status="success")
    payload = SimpleNamespace(environment="")
    log_steps: list[dict[str, str]] = []

    monkeypatch.setattr(TicketLogPullDao, "get_record_by_id", lambda db, record_id: record)
    monkeypatch.setattr(TicketLogPullService, "_build_retry_payload", lambda record: payload)
    monkeypatch.setattr(TicketLogPullService, "_log_chain_step", lambda *args, **kwargs: log_steps.append(kwargs))
    monkeypatch.setattr(
        TicketLogPullService,
        "create_log_pull_services",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("缺少环境信息时不应继续创建任务")),
    )

    result = TicketLogPullService.retry_log_pull_services(object(), 2011730395835392, DummyUser())

    assert result.is_success is False
    assert result.message == "当前记录缺少环境信息，无法重新拉取"
    assert log_steps[-1]["reason"] == "当前记录缺少环境信息，无法重新拉取"


def test_build_external_request_headers_wraps_credential_errors(monkeypatch):
    """凭证解析失败时，应透出更明确的日志拉取上下文错误。"""
    from modules.credential.service.credential_resolve_service import CredentialResolveService

    monkeypatch.setattr(
        CredentialResolveService,
        "resolve_http_headers",
        lambda db, binding_id, target_url: (_ for _ in ()).throw(ValueError("凭证已过期")),
    )

    with pytest.raises(ValueError, match="日志拉取外部接口凭证不可用：凭证已过期"):
        TicketLogPullService._build_external_request_headers(
            object(),
            {"credentialBindingId": "binding-1"},
            "https://example.com/api/logs",
        )


def test_auto_ai_submit_failure_records_reason_in_event_and_notification(monkeypatch):
    """自动 AI 提交被拒绝时，应将服务返回原因同时写入时间线和通知原因。"""

    class DummyDb:
        """模拟仅记录提交次数的数据库会话。"""

        def __init__(self):
            self.commit_count = 0

        def commit(self):
            """记录失败事件提交，避免线程会话关闭时回滚。"""
            self.commit_count += 1

    db = DummyDb()
    record = SimpleNamespace(
        id=2043149749595136,
        ticket_id=2043147524033536,
        command_content={
            "_automation": {
                "autoAiEnabled": True,
                "aiAgentCode": "agent-prod",
                "aiProviderCode": "openai-prod",
            }
        },
    )
    ticket = SimpleNamespace(ticket_id=record.ticket_id, affected_version_id=174076259444195365)
    chain_steps: list[dict] = []
    notifications: list[dict] = []

    monkeypatch.setattr(TicketLogPullDao, "get_record_by_id", lambda db, record_id: record)
    monkeypatch.setattr(
        "modules.ticket.service.log_pull.ticket_log_pull_service.TicketDao.get_ticket_by_id",
        lambda db, ticket_id: ticket,
    )
    monkeypatch.setattr(TicketLogPullService, "_extract_record_notify_config", lambda record: {})
    monkeypatch.setattr(TicketAutoAiAnalysisConditionService, "check_conditions", lambda *args, **kwargs: None)
    monkeypatch.setattr(TicketLogPullService, "_log_chain_step", lambda *args, **kwargs: chain_steps.append(kwargs))
    monkeypatch.setattr(
        TicketLogPullService,
        "_notify_automation",
        lambda *args, **kwargs: notifications.append(kwargs),
    )

    from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService

    monkeypatch.setattr(
        TicketAiAnalysisService,
        "create_analysis_task_services",
        lambda *args, **kwargs: SimpleNamespace(is_success=False, message="Agent[agent-prod]未连接服务端"),
    )

    TicketLogPullService._trigger_auto_ai_analysis(db, record.id)

    assert chain_steps == [
        {
            "ticket_id": record.ticket_id,
            "record_id": record.id,
            "step": "auto-ai",
            "status": "failed",
            "reason": "Agent[agent-prod]未连接服务端",
            "detail": {
                "versionId": ticket.affected_version_id,
                "agentCode": "agent-prod",
                "providerCode": "openai-prod",
                "failureStage": "submit",
            },
        }
    ]
    assert notifications[0]["message"] == "日志拉取后自动AI提交失败"
    assert notifications[0]["detail"] == "Agent[agent-prod]未连接服务端"
    assert db.commit_count == 1


def test_auto_ai_condition_uses_internal_ticket_status(monkeypatch):
    """启用状态过滤时只允许匹配内部状态编码。"""
    ticket = SimpleNamespace(ticket_id=1001, status="resolved")
    assert TicketAutoAiAnalysisConditionService.check_conditions(
        object(),
        ticket,
        {"analysisMode": "always", "statusFilterEnabled": True, "statusCodes": ["pending"]},
    )[0] == "工单状态不满足自动AI分析条件"


def test_auto_ai_condition_skips_after_successful_task(monkeypatch):
    """历史成功分析条件开启时，有成功记录则跳过自动分析。"""
    ticket = SimpleNamespace(ticket_id=1001, status="pending")
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service.TicketAiDao.get_last_successful_task_by_ticket",
        lambda db, ticket_id: SimpleNamespace(task_id=9001),
    )
    assert TicketAutoAiAnalysisConditionService.check_conditions(
        object(),
        ticket,
        {"analysisMode": "not_successful", "statusFilterEnabled": False, "statusCodes": []},
    )[0] == "工单已有成功的AI分析记录"


def test_auto_ai_condition_allows_failed_task_retry(monkeypatch):
    """最近一次任务失败时，自动分析仍允许重新提交。"""
    ticket = SimpleNamespace(ticket_id=1001, status="pending")
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service.TicketAiDao.get_last_successful_task_by_ticket",
        lambda db, ticket_id: None,
    )
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service.TicketAiDao.get_latest_task_by_ticket_id",
        lambda db, ticket_id: SimpleNamespace(task_id=9002, status="failed"),
    )
    assert TicketAutoAiAnalysisConditionService.check_conditions(
        object(),
        ticket,
        {"analysisMode": "not_successful", "statusFilterEnabled": False, "statusCodes": []},
    ) is None


def test_auto_ai_condition_skips_active_task(monkeypatch):
    """已有创建中或运行中的任务时，不重复提交自动分析。"""
    ticket = SimpleNamespace(ticket_id=1001, status="pending")
    monkeypatch.setattr(
        "modules.ticket.service.ai.ticket_auto_ai_analysis_condition_service.TicketAiDao.get_latest_task_by_ticket_id",
        lambda db, ticket_id: SimpleNamespace(task_id=9003, status="running"),
    )

    result = TicketAutoAiAnalysisConditionService.check_conditions(
        object(),
        ticket,
        {"analysisMode": "always", "statusFilterEnabled": False, "statusCodes": []},
    )

    assert result is not None
    assert result[0] == "工单已有正在执行的AI分析任务"


def test_find_matching_success_record_ignores_automation_snapshot(monkeypatch):
    """相同拉取参数即使命令内容中的通知和自动 AI 快照不同，也应命中成功记录。"""
    payload = TicketLogPullCreateModel.model_validate(
        {
            "ticketId": 1001,
            "environment": "prod",
            "vendorId": 11,
            "storeId": "552283",
            "posNo": 2,
            "commandDataType": 1,
            "modifyTime": "2026-08-20",
            "logBeginTime": "2026-08-20 10:00:00",
            "logEndTime": "2026-08-20 10:30:00",
            "autoAiEnabled": True,
            "aiAgentCode": "agent-a",
            "aiProviderCode": "provider-a",
            "notifyConfig": {"channel": "a"},
        }
    )
    matching_record = SimpleNamespace(
        id=2011730395835393,
        ticket_id=1001,
        status="success",
        environment="prod",
        vendor_id=11,
        store_id="552283",
        pos_no=2,
        command_data_type=1,
        command_content={
            "modifyTime": "2026-08-20",
            "logBeginTime": "2026-08-20 10:00:00",
            "logEndTime": "2026-08-20 10:30:00",
            "fileMaxSize": 500,
            "zipMaxSize": 500,
            "notifyConfig": {"channel": "b"},
            "_automation": {
                "autoAiEnabled": False,
                "aiAgentCode": "agent-b",
                "aiProviderCode": "provider-b",
            },
        },
        log_begin_time=datetime(2026, 8, 20, 10, 0, 0),
        log_end_time=datetime(2026, 8, 20, 10, 30, 0),
    )
    mismatched_record = SimpleNamespace(
        id=2011730395835394,
        ticket_id=1001,
        status="success",
        environment="prod",
        vendor_id=11,
        store_id="552283",
        pos_no=2,
        command_data_type=1,
        command_content={
            "modifyTime": "2026-08-21",
            "logBeginTime": "2026-08-21 10:00:00",
            "logEndTime": "2026-08-21 10:30:00",
            "fileMaxSize": 500,
            "zipMaxSize": 500,
        },
        log_begin_time=datetime(2026, 8, 21, 10, 0, 0),
        log_end_time=datetime(2026, 8, 21, 10, 30, 0),
    )

    monkeypatch.setattr(
        TicketLogPullDao,
        "list_success_records_by_pull_identity",
        lambda *args, **kwargs: [mismatched_record, matching_record],
    )

    result = TicketLogPullService.find_matching_success_record(object(), 1001, payload)

    assert result is matching_record


def test_sync_config_normalizes_auto_log_pull_stop_condition():
    """自动拉日志停止条件应完成去重、裁剪和布尔归一化。"""
    normalized = TicketSyncConfigService.normalize_sync_config(
        {
            "logPullDefaults": {
                "autoLogPullStopCondition": {
                    "enabled": 1,
                    "statusCodes": [" wait_dev ", "", None, "wait_dev", "resolved"],
                    "cancelActiveRecords": 0,
                }
            }
        }
    )

    condition = normalized["logPullDefaults"]["autoLogPullStopCondition"]
    assert condition == {
        "enabled": True,
        "statusCodes": ["wait_dev", "resolved"],
        "cancelActiveRecords": False,
    }
    match = TicketSyncConfigService.match_auto_log_pull_stop_condition("resolved", normalized)
    assert match["matched"] is True
    assert match["ticketStatus"] == "resolved"



def test_create_log_pull_services_persists_automation_snapshot(monkeypatch):
    """创建日志拉取记录时应把自动化快照写入 command_content。"""

    class DummyDb:
        def __init__(self):
            self.commit_count = 0

        def commit(self):
            self.commit_count += 1

    db = DummyDb()
    captured: dict[str, object] = {}

    monkeypatch.setattr(TicketLogPullService, "_get_storage_config_dict", lambda query_db: {"mode": "local"})
    monkeypatch.setattr(TicketLogPullService, "_add_ticket_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(TicketLogPullService, "_log_chain_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(TicketLogPullService, "queue_record", lambda record_id: None)
    monkeypatch.setattr(
        "modules.ticket.service.log_pull.ticket_log_pull_service.TicketDao.get_ticket_by_id",
        lambda query_db, ticket_id: SimpleNamespace(ticket_id=ticket_id),
    )

    def fake_add_record(query_db, record):
        record.id = 2043149749595137
        captured["record"] = record
        return record

    monkeypatch.setattr(TicketLogPullDao, "add_record", fake_add_record)

    payload = TicketLogPullCreateModel.model_validate(
        {
            "ticketId": 1001,
            "environment": "prod",
            "vendorId": 11,
            "storeId": "552283",
            "posNo": 2,
            "commandDataType": 1,
            "modifyTime": "2026-08-20",
            "logBeginTime": "2026-08-20 10:00:00",
            "logEndTime": "2026-08-20 10:30:00",
            "autoAiEnabled": True,
            "aiProviderCode": "provider-a",
            "notifyConfig": {"channel": "a"},
            "automationSnapshot": {
                "autoCreated": True,
                "notifyConfig": {"channel": "a"},
            },
        }
    )

    result = TicketLogPullService.create_log_pull_services(db, 1001, payload, DummyUser())

    assert result.is_success is True
    record = captured["record"]
    assert record.command_content["notifyConfig"] == {"channel": "a"}
    assert record.command_content["_automation"]["autoCreated"] is True
    assert record.command_content["_automation"]["autoAiEnabled"] is True
    assert db.commit_count == 1



def test_cancel_auto_created_active_records_by_ticket_status_only_cancels_auto_records(monkeypatch):
    """命中停止条件后，只应停止自动创建的活动日志记录。"""

    class DummyDb:
        def __init__(self):
            self.commit_count = 0

        def commit(self):
            self.commit_count += 1

    db = DummyDb()
    auto_record = SimpleNamespace(
        id=2043149749595138,
        ticket_id=1001,
        status="created",
        command_content={"_automation": {"autoCreated": True}},
    )
    manual_record = SimpleNamespace(
        id=2043149749595139,
        ticket_id=1001,
        status="created",
        command_content={},
    )
    updated_records: list[tuple[int, dict]] = []
    event_calls: list[dict] = []
    log_calls: list[dict] = []

    monkeypatch.setattr(
        TicketLogPullDao,
        "list_active_records_by_ticket_id",
        lambda query_db, ticket_id, statuses: [auto_record, manual_record],
    )
    monkeypatch.setattr(
        TicketLogPullDao,
        "update_record",
        lambda query_db, record_id, data: updated_records.append((record_id, data)),
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "_add_ticket_event",
        lambda *args, **kwargs: event_calls.append(kwargs),
    )
    monkeypatch.setattr(
        TicketLogPullService,
        "_log_chain_step",
        lambda *args, **kwargs: log_calls.append(kwargs),
    )

    result = TicketLogPullService.cancel_auto_created_active_records_by_ticket_status(
        db,
        ticket_id=1001,
        ticket_status="wait_dev",
        operator_name="tester",
        operator_id=7,
        config={
            "logPullDefaults": {
                "autoLogPullStopCondition": {
                    "enabled": True,
                    "statusCodes": ["wait_dev", "resolved"],
                    "cancelActiveRecords": True,
                }
            }
        },
        trigger_source="ticket_status_change",
    )

    assert result["cancelledRecordIds"] == [2043149749595138]
    assert updated_records[0][0] == 2043149749595138
    assert updated_records[0][1]["status"] == "cancelled"
    assert event_calls[0]["event_data"]["trigger_source"] == "ticket_status_change"
    assert log_calls[0]["status"] == "cancelled"
    assert db.commit_count == 1
