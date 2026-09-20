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
from modules.configuration_task.dao.stage_artifact_dao import ConfigurationTaskStageDao
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


def test_retry_write_stage_requires_reapproval(db_session):
    """WRITE 阶段重试后必须重新进入审批等待。"""
    stages = _run_with_stages(db_session, write_mode=True)
    write_stage = stages[1]
    ConfigurationTaskStageDao.update_run_stage(
        db_session, write_stage.run_stage_id, {"status": "FAILED", "error_code": "STEP_FAILED"}
    )
    db_session.commit()
    result = ConfigurationTaskStageService.retry_stage(db_session, write_stage.run_stage_id, _current_user())
    assert result.is_success is True
    assert result.result.status == "WAITING_APPROVAL"
    assert result.result.model_dump(by_alias=True)["retryCount"] == 1


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

    # 重复上报同一截图应返回同一资源（幂等）。
    again = ConfigurationTaskArtifactService.register_agent_screenshot(db_session, model, _current_user())
    assert again.is_success is True
    assert again.result.model_dump(by_alias=True)["resourceId"] == result.result.model_dump(by_alias=True)["resourceId"]
    assert db_session.query(TaskArtifact).count() == 2
