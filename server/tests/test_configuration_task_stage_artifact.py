"""配置任务阶段、审批闸门与产物测试。"""

import base64
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import Base
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.dao.stage_artifact_dao import (
    ConfigurationTaskStageDao,
    TaskArtifactDao,
)
from modules.configuration_task.dao.task_dao import ConfigurationTaskRunDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.stage_artifact_do import (
    ConfigurationTaskStage,
    TaskArtifact,
    TaskRunStage,
)
from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import AgentStepScreenshotModel, StageApproveModel
from modules.configuration_task.service.artifact_service import ConfigurationTaskArtifactService
from modules.configuration_task.service.evidence_status_service import (
    ConfigurationTaskEvidenceStatusService,
)
from modules.configuration_task.service.stage_service import ConfigurationTaskStageService

TASK_ID = 700000000000001
VERSION_ID = 700000000000002
RUN_ID = 700000000000003


@pytest.fixture(autouse=True)
def fake_registered_agent(monkeypatch):
    """默认 Agent 已登记。"""

    class _FakeAgent:
        agent_id = 1
        agent_code = "agent-01"

    monkeypatch.setattr(AgentDao, "get_agent_by_code", staticmethod(lambda db, code: _FakeAgent()))
    yield


@pytest.fixture
def db_session():
    """创建阶段产物测试所需的 SQLite 会话。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ConfigurationTask.__table__,
            ConfigurationTaskVersion.__table__,
            ConfigurationTaskRun.__table__,
            ResourceObject.__table__,
            ConfigurationTaskStage.__table__,
            TaskRunStage.__table__,
            TaskArtifact.__table__,
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user():
    """构造审批操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="approver", admin=False))


def _run_with_stages(db, write_mode=True):
    """创建运行和两阶段快照（READ + WRITE/READ）。"""
    now = datetime.now()
    db.add(
        ConfigurationTask(
            task_id=TASK_ID,
            task_name="阶段任务",
            agent_code="agent-01",
            status="ACTIVE",
            create_time=now,
            update_time=now,
        )
    )
    db.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            status="RUNNING",
            started_at=now,
            create_time=now,
            update_time=now,
        )
    )
    stages = [
        {
            "task_run_id": RUN_ID,
            "stage_id": 1,
            "stage_key": "query",
            "stage_name": "查询",
            "mode": "READ",
            "stage_order": 1,
            "step_range_json": "[0,1]",
            "status": "PENDING",
            "create_time": now,
            "update_time": now,
        },
        {
            "task_run_id": RUN_ID,
            "stage_id": 2,
            "stage_key": "save",
            "stage_name": "保存",
            "mode": "WRITE" if write_mode else "READ",
            "stage_order": 2,
            "step_range_json": "[2]",
            "status": "WAITING_APPROVAL" if write_mode else "PENDING",
            "create_time": now,
            "update_time": now,
        },
    ]
    rows = ConfigurationTaskStageDao.add_run_stages(db, stages)
    db.commit()
    return rows


def test_snapshot_run_stages_single_stage_fallback(db_session):
    """版本未声明阶段时，快照应生成单一全量阶段（保持向后兼容）。"""
    _run_with_stages(db_session, write_mode=False)
    db_session.add(
        ConfigurationTaskVersion(
            version_id=VERSION_ID,
            task_id=TASK_ID,
            version_no=1,
            status="PUBLISHED",
            create_time=datetime.now(),
            update_time=datetime.now(),
        )
    )
    db_session.commit()
    run = ConfigurationTaskRunDao.get_run(db_session, RUN_ID)
    version = SimpleNamespace(version_id=VERSION_ID)
    ConfigurationTaskStageService.snapshot_run_stages(db_session, run, version)
    stages = ConfigurationTaskStageService.list_run_stages(db_session, RUN_ID)
    assert any(
        stage.model_dump(by_alias=True)["stageKey"] == "all" and stage.mode == "READ" for stage in stages
    )


def test_approve_write_stage_rejection_cancels_run(db_session):
    """WRITE 阶段审批拒绝时，阶段与运行都收敛取消。"""
    stages = _run_with_stages(db_session, write_mode=True)
    write_stage = stages[1]
    result = ConfigurationTaskStageService.approve_stage(
        db_session, write_stage.run_stage_id, StageApproveModel(approved=False), _current_user()
    )
    assert result.is_success is False
    run = ConfigurationTaskRunDao.get_run(db_session, RUN_ID)
    assert run.status == "CANCELLED"
    assert run.error_code == "STAGE_REJECTED"


def test_approve_write_stage_acceptance_resets_to_pending(db_session):
    """WRITE 阶段审批通过后回到 PENDING 等待执行，并记录审批人。"""
    stages = _run_with_stages(db_session, write_mode=True)
    write_stage = stages[1]
    result = ConfigurationTaskStageService.approve_stage(
        db_session, write_stage.run_stage_id, StageApproveModel(approved=True), _current_user()
    )
    assert result.is_success is True
    assert result.result.status == "PENDING"
    assert result.result.model_dump(by_alias=True)["approvedBy"] == "approver"


def test_stage_failure_skips_later_stages(db_session):
    """阶段失败时后续阶段自动 SKIPPED。"""
    stages = _run_with_stages(db_session, write_mode=True)
    ConfigurationTaskStageService.mark_stage_running(db_session, stages[0].run_stage_id)
    ConfigurationTaskStageService.mark_stage_finished(
        db_session, stages[0].run_stage_id, False, {}, error_code="STEP_FAILED", error_message="失败"
    )
    rows = {
        row.model_dump(by_alias=True)["stageKey"]: row
        for row in ConfigurationTaskStageService.list_run_stages(db_session, RUN_ID)
    }
    assert rows["query"].status == "FAILED"
    assert rows["save"].status == "SKIPPED"


def test_stage_success_refreshes_evidence_status(db_session):
    """阶段成功终态也要立即重算证据状态，不能继续显示 PENDING。"""
    stages = _run_with_stages(db_session, write_mode=False)
    query_stage = stages[0]
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        query_stage.run_stage_id,
        {
            "step_ids_json": '["step-before"]',
            "evidence_policy_json": '{"mode":"REQUIRED","requiredTypes":["before_screenshot"]}',
        },
    )
    run = db_session.get(ConfigurationTaskRun, RUN_ID)
    run.run_params_json = (
        '{"evidencePlan":{"steps":{"step-before":'
        '{"evidenceType":"before_screenshot","evidenceKey":"before"}}}}'
    )
    db_session.commit()

    ConfigurationTaskStageService.mark_stage_finished(
        db_session,
        query_stage.run_stage_id,
        True,
        {"lastStep": {"stepId": "step-before", "status": "success"}},
    )

    refreshed = db_session.get(TaskRunStage, query_stage.run_stage_id)
    assert refreshed.status == "SUCCESS"
    assert refreshed.evidence_status == "INCOMPLETE"
    assert "before_screenshot" in refreshed.evidence_missing_json


def test_retry_stage_resets_evidence_status(db_session):
    """阶段重试必须清空上一次尝试的证据状态和缺失摘要。"""
    stages = _run_with_stages(db_session, write_mode=False)
    failed_stage = stages[0]
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        failed_stage.run_stage_id,
        {
            "status": "FAILED",
            "evidence_status": "INCOMPLETE",
            "evidence_missing_json": '[{"evidenceKey":"before"}]',
        },
    )
    db_session.commit()

    result = ConfigurationTaskStageService.retry_stage(
        db_session,
        failed_stage.run_stage_id,
        _current_user(),
    )

    assert result.is_success is True
    assert result.result.evidence_status == "PENDING"
    assert result.result.evidence_missing == []


def test_retry_stage_clears_previous_execution_fields(db_session):
    """阶段重试必须清空上一轮结果、时间和错误字段。"""
    stages = _run_with_stages(db_session, write_mode=False)
    failed_stage = stages[0]
    started_at = datetime(2025, 1, 1)
    ended_at = datetime(2025, 1, 2)
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        failed_stage.run_stage_id,
        {
            "status": "FAILED",
            "result_json": '{"old":true}',
            "error_code": "OLD_ERROR",
            "error_message": "旧错误",
            "started_at": started_at,
            "ended_at": ended_at,
        },
    )
    db_session.commit()

    result = ConfigurationTaskStageService.retry_stage(
        db_session,
        failed_stage.run_stage_id,
        _current_user(),
    )

    assert result.is_success is True
    row = db_session.get(TaskRunStage, failed_stage.run_stage_id)
    assert row.status == "PENDING"
    assert row.result_json == "{}"
    assert row.error_code == ""
    assert row.error_message == ""
    assert row.started_at is None
    assert row.ended_at is None


def test_retry_stage_rejects_terminal_run(db_session):
    """所属运行已经终态时，不能重新打开失败阶段。"""
    stages = _run_with_stages(db_session, write_mode=False)
    failed_stage = stages[0]
    run = db_session.get(ConfigurationTaskRun, RUN_ID)
    run.status = "CANCELLED"
    run.business_status = "CANCELLED"
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        failed_stage.run_stage_id,
        {"status": "FAILED"},
    )
    db_session.commit()

    result = ConfigurationTaskStageService.retry_stage(
        db_session,
        failed_stage.run_stage_id,
        _current_user(),
    )

    assert result.is_success is False
    assert "不允许重试" in result.message
    db_session.refresh(failed_stage)
    assert failed_stage.status == "FAILED"


def test_mark_stage_finished_is_terminal_idempotent(db_session):
    """阶段已终态时，迟到成功/失败事件均不能覆盖原结果。"""
    stages = _run_with_stages(db_session, write_mode=False)
    stage = stages[0]
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        stage.run_stage_id,
        {
            "status": "SUCCESS",
            "result_json": '{"winner":"success"}',
            "error_code": "",
            "error_message": "",
        },
    )
    db_session.commit()

    ConfigurationTaskStageService.mark_stage_finished(
        db_session,
        stage.run_stage_id,
        False,
        {"winner": "late-failure"},
        error_code="LATE_FAILURE",
        error_message="迟到失败",
    )

    row = db_session.get(TaskRunStage, stage.run_stage_id)
    assert row.status == "SUCCESS"
    assert row.result_json == '{"winner":"success"}'
    assert row.error_code == ""
    assert row.error_message == ""


def test_write_stage_retry_returns_to_approval(db_session):
    """WRITE 阶段重试必须清理审批信息并重新等待审批。"""
    stages = _run_with_stages(db_session, write_mode=True)
    stage = stages[1]
    ConfigurationTaskStageDao.update_run_stage(
        db_session,
        stage.run_stage_id,
        {
            "status": "FAILED",
            "approved_by": "approver",
            "approved_at": datetime.now(),
            "result_json": '{"old":true}',
        },
    )
    db_session.commit()

    result = ConfigurationTaskStageService.retry_stage(db_session, stage.run_stage_id, _current_user())

    assert result.is_success is True
    assert result.result.status == "WAITING_APPROVAL"
    row = db_session.get(TaskRunStage, stage.run_stage_id)
    assert row.approved_by == ""
    assert row.approved_at is None
    assert row.result_json == "{}"


def test_required_type_accepts_any_matching_artifact(db_session):
    """requiredTypes 只要求该类型至少一项，多个同类型步骤不必全部上报。"""
    candidates = [
        {
            "evidenceType": "before_screenshot",
            "evidenceKey": "before-1",
            "sequenceNo": 1,
            "required": True,
        },
        {
            "evidenceType": "before_screenshot",
            "evidenceKey": "before-2",
            "sequenceNo": 1,
            "required": True,
        },
    ]

    expected = ConfigurationTaskEvidenceStatusService._build_expected_items(
        "REQUIRED",
        {"requiredTypes": ["before_screenshot"]},
        candidates,
    )

    assert len(expected) == 1
    assert expected[0]["evidenceType"] == "before_screenshot"
    assert expected[0]["evidenceKey"] == ""
    assert expected[0]["sequenceNo"] is None

    matching_artifact = SimpleNamespace(
        evidence_type="before_screenshot",
        artifact_type="step_screenshot",
        evidence_key="before-2",
        sequence_no=1,
        availability_status="ONLINE",
    )
    assert ConfigurationTaskEvidenceStatusService._artifact_matches(
        matching_artifact, expected[0]
    )


def test_register_agent_screenshot_recovers_reference_unique_conflict(db_session, monkeypatch):
    """插入前查询竞态触发唯一键冲突时，应回查并返回已有引用。"""
    _run_with_stages(db_session, write_mode=False)
    payload = base64.b64encode(b"concurrent-screenshot").decode("ascii")
    model = AgentStepScreenshotModel(
        taskRunId=str(RUN_ID),
        stepIndex=2,
        stepName="并发截图",
        artifactType="step_screenshot",
        stageKey="query",
        data=payload,
    )
    first = ConfigurationTaskArtifactService.register_agent_screenshot(
        db_session, model, _current_user()
    )
    assert first.is_success is True

    original_get = TaskArtifactDao.get_artifact_by_evidence_identity
    query_count = 0

    def hide_existing_once(db, task_run_id, run_stage_id, step_id, evidence_key, sequence_no, sha256):
        nonlocal query_count
        query_count += 1
        if query_count == 1:
            return None
        return original_get(
            db,
            task_run_id,
            run_stage_id,
            step_id,
            evidence_key,
            sequence_no,
            sha256,
        )

    monkeypatch.setattr(
        TaskArtifactDao,
        "get_artifact_by_evidence_identity",
        staticmethod(hide_existing_once),
    )
    second = ConfigurationTaskArtifactService.register_agent_screenshot(
        db_session, model, _current_user()
    )

    assert second.is_success is True
    assert second.result.model_dump(by_alias=True)["artifactId"] == first.result.model_dump(
        by_alias=True
    )["artifactId"]
    assert db_session.query(TaskArtifact).count() == 1


def test_register_agent_screenshot_creates_resource_and_artifact(db_session):
    """Agent 截图上报应同时登记 READY 资源和产物引用；重复上报幂等。"""
    _run_with_stages(db_session, write_mode=False)
    png_bytes = b"\x89PNG\r\n\x1a\nfake-image"
    payload = base64.b64encode(png_bytes).decode("ascii")
    model = AgentStepScreenshotModel(
        taskRunId=str(RUN_ID),
        stepIndex=2,
        stepName="保存配置",
        artifactType="failure_screenshot",
        data=payload,
    )
    result = ConfigurationTaskArtifactService.register_agent_screenshot(db_session, model, _current_user())
    assert result.is_success is True
    assert result.result.model_dump(by_alias=True)["artifactType"] == "failure_screenshot"
    assert result.result.model_dump(by_alias=True)["fileSize"] == len(png_bytes)

    # 旧版 Agent 未携带证据扩展字段时，仍按 Base64 正文登记资源；引用本身也应幂等。
    assert db_session.query(TaskArtifact).count() == 1


def test_register_agent_screenshot_reference_is_idempotent(db_session):
    """同一运行、步骤和证据引用重复上报时，不应产生重复 task_artifact。"""
    _run_with_stages(db_session, write_mode=False)
    payload = base64.b64encode(b"same-screenshot").decode("ascii")
    model = AgentStepScreenshotModel(
        taskRunId=str(RUN_ID),
        stepIndex=2,
        stepName="查询结果",
        artifactType="step_screenshot",
        data=payload,
    )

    first = ConfigurationTaskArtifactService.register_agent_screenshot(db_session, model, _current_user())
    second = ConfigurationTaskArtifactService.register_agent_screenshot(db_session, model, _current_user())

    assert first.is_success is True
    assert second.is_success is True
    assert second.result.model_dump(by_alias=True)["resourceId"] == first.result.model_dump(by_alias=True)["resourceId"]
    assert db_session.query(TaskArtifact).count() == 1
