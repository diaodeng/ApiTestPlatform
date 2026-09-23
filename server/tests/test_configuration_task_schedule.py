"""配置任务定时触发与调度配置测试。"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import Base
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.stage_artifact_do import ConfigurationTaskStage, TaskRunStage
from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import TaskScheduleModel
from modules.configuration_task.service.task_schedule_service import (
    ConfigurationTaskScheduleService,
)

TASK_ID = 500000000000001


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
    """创建调度测试所需的 SQLite 会话。"""
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
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def _user():
    """构造操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester", admin=False))


def _task(db, remark=""):
    """写入测试任务。"""
    from datetime import datetime

    now = datetime.now()
    row = ConfigurationTask(
        task_id=TASK_ID,
        task_name="调度任务",
        agent_code="agent-01",
        status="ACTIVE",
        remark=remark,
        create_time=now,
        update_time=now,
    )
    db.add(row)
    db.commit()
    return row


def test_cron_validation_requires_five_fields():
    """cron 必须是 5 字段表达式。"""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        TaskScheduleModel(enabled=True, cron="0 9 * *")
    model = TaskScheduleModel(enabled=True, cron="0 9 * * *")
    assert model.cron == "0 9 * * *"


def _published_version(db, version_no=1):
    """写入已发布版本并设置任务当前版本指针。"""
    from datetime import datetime

    db.add(
        ConfigurationTaskVersion(
            version_id=version_no,
            task_id=TASK_ID,
            version_no=version_no,
            status="PUBLISHED",
            start_url="https://example.test/",
            steps_json='[{"stepKey":"s1","actionType":"click","enabled":true}]',
            publish_time=datetime.now(),
            create_time=datetime.now(),
            update_time=datetime.now(),
        )
    )
    task = db.get(ConfigurationTask, TASK_ID)
    task.current_version_id = version_no
    task.current_version_no = version_no
    db.commit()


def test_save_and_get_schedule_roundtrip(db_session):
    """调度配置保存后可完整读回，且保留 remark 其他内容。"""
    _task(db_session, remark="业务备注")
    _published_version(db_session)
    result = ConfigurationTaskScheduleService.save_schedule(
        db_session,
        TASK_ID,
        TaskScheduleModel(enabled=True, cron="0 9 * * 1-5"),
        _user(),
    )
    assert result.is_success is True
    schedule = ConfigurationTaskScheduleService.get_schedule(db_session, TASK_ID)
    assert schedule.enabled is True
    assert schedule.cron == "0 9 * * 1-5"
    # remark 业务内容保留在调度段之后。
    task = db_session.get(ConfigurationTask, TASK_ID)
    assert "业务备注" in task.remark


def test_save_schedule_requires_published_version(db_session):
    """启用定时时引用未发布版本必须被拒绝。"""
    _task(db_session)
    result = ConfigurationTaskScheduleService.save_schedule(
        db_session,
        TASK_ID,
        TaskScheduleModel(enabled=True, cron="0 9 * * *", versionNo=9),
        _user(),
    )
    assert result.is_success is False
    assert "未发布" in result.message


def test_save_schedule_requires_cron_when_enabled(db_session):
    """启用定时时 cron 必填。"""
    _task(db_session)
    result = ConfigurationTaskScheduleService.save_schedule(
        db_session,
        TASK_ID,
        TaskScheduleModel(enabled=True),
        _user(),
    )
    assert result.is_success is False
    assert "cron" in result.message


def test_trigger_skips_when_disabled(db_session, monkeypatch):
    """未启用定时触发时直接跳过，不创建运行。"""
    _task(db_session)
    summary = ConfigurationTaskScheduleService.trigger_scheduled_run(db_session, TASK_ID)
    assert summary["is_success"] is False
    assert "未启用" in summary["message"]
    assert db_session.query(ConfigurationTaskRun).count() == 0


def test_trigger_executes_run_when_enabled(db_session, monkeypatch):
    """启用定时触发后按调度配置执行一次运行。"""
    _task(db_session)
    # 先有已发布版本才能启用定时。
    _published_version(db_session)
    ConfigurationTaskScheduleService.save_schedule(
        db_session,
        TASK_ID,
        TaskScheduleModel(enabled=True, cron="0 9 * * *"),
        _user(),
    )

    # 拦截 Agent 下发，直接返回成功响应。
    import modules.configuration_task.service.task_run_service as run_module

    class _FakeResponse:
        status_code = 200
        message = "操作成功"
        response = {"success": True, "status": "success", "result": {"steps": []}, "message": "操作成功"}

    async def fake_send(agent_code, message, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(run_module, "send_message", fake_send)
    summary = ConfigurationTaskScheduleService.trigger_scheduled_run(db_session, TASK_ID)
    assert summary["is_success"] is True
    assert summary["taskRunId"]
    run_row = db_session.query(ConfigurationTaskRun).one()
    assert run_row.trigger_type == "scheduled"
    assert run_row.status == "SUCCESS"
