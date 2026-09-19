"""配置任务运行域最小闭环测试：任务、版本发布与运行执行。"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.database import Base
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.task_do import ConfigurationTask, ConfigurationTaskVersion
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import (
    TaskRunCreateModel,
)
from modules.configuration_task.service.task_run_service import ConfigurationTaskRunService
from modules.configuration_task.service.task_service import ConfigurationTaskService

TASK_ID = 800000000000001
VERSION_ID = 800000000000002
RUN_ID = 800000000000003
RESOURCE_ID = 800000000000004
SHA256 = "c" * 64


@pytest.fixture(autouse=True)
def fake_registered_agent(monkeypatch):
    """所有用例默认 Agent 已登记，避免在 SQLite 中创建 qtr_agent 表。"""

    class _FakeAgent:
        agent_id = 1
        agent_code = "agent-01"

    monkeypatch.setattr(AgentDao, "get_agent_by_code", staticmethod(lambda db, code: _FakeAgent()))
    yield


@pytest.fixture
def db_session():
    """创建运行域测试所需的 SQLite 会话。

    运行服务会把同步 DB 段放到 run_in_threadpool 的工作线程执行，
    SQLite 内存库必须用 StaticPool 共享单连接，否则工作线程拿到的是空库。
    """
    from sqlalchemy.pool import StaticPool

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
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user():
    """构造非管理员任务操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester", admin=False))


def _task(db):
    """写入测试任务实体；Agent 登记通过 monkeypatch 替换查询。"""
    now = datetime.now()
    row = ConfigurationTask(
        task_id=TASK_ID,
        task_name="门店查询任务",
        agent_code="agent-01",
        variables_json="{}",
        status="ACTIVE",
        create_by="tester",
        create_time=now,
        update_by="tester",
        update_time=now,
    )
    db.add(row)
    db.commit()
    return row


def _version(db, status="PUBLISHED", bindings=None):
    """写入测试版本实体，默认含一个资源绑定并已发布。"""
    if bindings is None:
        bindings = f'{{"price_tag": ["{RESOURCE_ID}"]}}'
    now = datetime.now()
    row = ConfigurationTaskVersion(
        version_id=VERSION_ID,
        task_id=TASK_ID,
        version_no=1,
        status=status,
        start_url="https://example.test/store",
        browser_name="chromium",
        headless=True,
        credential_binding_id="",
        variables_json="{}",
        steps_json='[{"stepKey":"s1","actionType":"click","enabled":true}]',
        input_bindings_json=bindings,
        publish_by="tester",
        publish_time=now if status == "PUBLISHED" else None,
        create_by="tester",
        create_time=now,
        update_by="tester",
        update_time=now,
    )
    db.add(row)
    db.commit()
    # 已发布版本同步设置任务当前版本指针，模拟发布服务完成后的状态。
    if status == "PUBLISHED":
        task = db.get(ConfigurationTask, TASK_ID)
        task.current_version_id = VERSION_ID
        task.current_version_no = 1
        db.commit()
    return row


def _resource(db, status="READY", agent_code="agent-01"):
    """写入测试资源实体。"""
    now = datetime.now()
    row = ResourceObject(
        resource_id=RESOURCE_ID,
        provider_type="agent_local",
        provider_execution_side="agent",
        agent_code=agent_code,
        object_key="inputs/demo.txt",
        original_file_name="demo.txt",
        mime_type="text/plain",
        file_size=3,
        checksum_algorithm="sha256",
        sha256=SHA256,
        version=1,
        status=status,
        create_by="tester",
        create_time=now,
        update_by="tester",
        update_time=now,
    )
    db.add(row)
    db.commit()
    return row


def test_publish_version_rejects_not_ready_resource(db_session):
    """发布版本时绑定资源未就绪必须被拒绝。"""
    _task(db_session)
    _resource(db_session, status="PENDING")
    version = _version(db_session, status="DRAFT")
    result = ConfigurationTaskService.publish_version(db_session, version.version_id, _current_user())
    assert result.is_success is False
    assert "未就绪" in result.message
    assert db_session.get(ConfigurationTaskVersion, version.version_id).status == "DRAFT"


def test_publish_version_rejects_resource_from_other_agent(db_session):
    """发布版本时资源不属于任务 Agent 必须被拒绝。"""
    _task(db_session)
    _resource(db_session, agent_code="agent-other")
    version = _version(db_session, status="DRAFT")
    result = ConfigurationTaskService.publish_version(db_session, version.version_id, _current_user())
    assert result.is_success is False
    assert "不属于执行Agent" in result.message


def test_publish_version_success_updates_task_pointer(db_session):
    """发布成功后版本状态和任务当前版本指针必须更新。"""
    task = _task(db_session)
    _resource(db_session)
    version = _version(db_session, status="DRAFT")
    result = ConfigurationTaskService.publish_version(db_session, version.version_id, _current_user())
    assert result.is_success is True
    refreshed_task = db_session.get(ConfigurationTask, task.task_id)
    refreshed_version = db_session.get(ConfigurationTaskVersion, version.version_id)
    assert refreshed_task.current_version_id == version.version_id
    assert refreshed_version.status == "PUBLISHED"


def test_run_rejects_unpublished_version(db_session):
    """运行未发布版本必须被拒绝且不创建运行记录。"""
    _task(db_session)
    _resource(db_session)
    _version(db_session, status="DRAFT")
    result = asyncio.run(
        ConfigurationTaskRunService.create_run_and_execute(
            db_session, TASK_ID, TaskRunCreateModel(versionNo=1), _current_user()
        )
    )
    assert result.is_success is False
    assert "未发布" in result.message
    assert db_session.query(ConfigurationTaskRun).count() == 0


def test_run_rejects_resource_not_ready(db_session):
    """运行时资源未就绪必须被拒绝且不创建运行记录。"""
    _task(db_session)
    _resource(db_session, status="FAILED")
    _version(db_session)
    result = asyncio.run(
        ConfigurationTaskRunService.create_run_and_execute(
            db_session, TASK_ID, TaskRunCreateModel(), _current_user()
        )
    )
    assert result.is_success is False
    assert "未就绪" in result.message
    assert db_session.query(ConfigurationTaskRun).count() == 0


def test_run_success_flows_to_terminal_state(db_session, monkeypatch):
    """运行成功路径：快照冻结、run_case 注入 resourceBindings、终态 SUCCESS。"""
    task = _task(db_session)
    _resource(db_session)
    _version(db_session)
    captured = {}

    def fake_send(agent_code, message, **kwargs):
        captured["agent_code"] = agent_code
        captured["message"] = message
        return _FakeResponse(success=True, result={"steps": [{"status": "passed"}]})

    async def async_send(agent_code, message, **kwargs):
        return fake_send(agent_code, message, **kwargs)

    monkeypatch.setattr(
        "modules.configuration_task.service.task_run_service.send_message",
        async_send,
    )
    result = asyncio.run(
        ConfigurationTaskRunService.create_run_and_execute(
            db_session, TASK_ID, TaskRunCreateModel(), _current_user()
        )
    )
    assert result.is_success is True
    assert result.result.status == "SUCCESS"
    assert captured["message"]["command"] == "run_case"
    bindings = captured["message"]["runtimeOptions"]["resourceBindings"]
    assert bindings == {"price_tag": [str(RESOURCE_ID)]}
    run_row = db_session.query(ConfigurationTaskRun).one()
    assert run_row.task_version_id == VERSION_ID
    assert run_row.status == "SUCCESS"
    assert run_row.input_snapshot_json
    assert run_row.task_id == task.task_id


def test_run_agent_failure_flows_to_failed(db_session, monkeypatch):
    """Agent 返回失败时运行必须落 FAILED 终态并保存错误信息。"""
    _task(db_session)
    _resource(db_session)
    _version(db_session)

    def fake_send(agent_code, message, **kwargs):
        return _FakeResponse(success=False, result={"steps": [{"status": "failed"}]}, message="页面断言失败")

    async def async_send(agent_code, message, **kwargs):
        return fake_send(agent_code, message, **kwargs)

    monkeypatch.setattr(
        "modules.configuration_task.service.task_run_service.send_message",
        async_send,
    )
    result = asyncio.run(
        ConfigurationTaskRunService.create_run_and_execute(
            db_session, TASK_ID, TaskRunCreateModel(), _current_user()
        )
    )
    assert result.is_success is False
    assert result.result.status == "FAILED"
    run_row = db_session.query(ConfigurationTaskRun).one()
    assert run_row.status == "FAILED"
    assert run_row.error_message == "页面断言失败"


class _FakeResponse:
    """模拟 Agent 网关统一响应结构；response 使用 dict 形态供提取逻辑解析。"""

    def __init__(self, success: bool, result: dict, message: str = "操作成功"):
        self.status_code = 200
        self.message = message
        self.response = {
            "success": success,
            "status": "success" if success else "failed",
            "result": result,
            "message": message,
        }
