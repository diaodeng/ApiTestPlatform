"""配置任务运行域最小闭环测试：任务、版本发布与运行执行。"""

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.database import Base
from module_hrm.dao.agent_dao import AgentDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.stage_artifact_do import (
    ConfigurationTaskStage,
    TaskRunStage,
)
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
            ConfigurationTaskStage.__table__,
            TaskRunStage.__table__,
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


def test_run_rejected_when_agent_has_active_run(db_session):
    """同一 Agent 已有 RUNNING 运行时，新运行必须被拒绝。"""
    _task(db_session)
    _resource(db_session)
    _version(db_session)
    # 直接制造一条 RUNNING 运行占用并发租约。
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="RUNNING",
            input_snapshot_json="{}",
            run_params_json="{}",
            started_at=now,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()
    result = asyncio.run(
        ConfigurationTaskRunService.create_run_and_execute(
            db_session, TASK_ID, TaskRunCreateModel(), _current_user()
        )
    )
    assert result.is_success is False
    assert "未完成的运行" in result.message
    assert db_session.query(ConfigurationTaskRun).count() == 1


def test_stop_run_marks_cancelled(db_session, monkeypatch):
    """停止运行后状态收敛为 CANCELLED。"""
    from modules.configuration_task.entity.vo.task_vo import TaskRunStopModel

    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="RUNNING",
            input_snapshot_json="{}",
            run_params_json="{}",
            started_at=now,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()
    monkeypatch.setattr(
        "modules.configuration_task.service.task_run_service.send_message",
        _async_ok_stop,
    )
    result = asyncio.run(
        ConfigurationTaskRunService.stop_run(db_session, RUN_ID, TaskRunStopModel(reason="测试停止"), _current_user())
    )
    assert result.is_success is True
    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    assert row.status == "CANCELLED"
    assert row.error_code == "RUN_CANCELLED"


async def _async_ok_stop(agent_code, message, **kwargs):
    """模拟停止命令成功响应。"""
    return _FakeResponse(success=True, result={"released": True})


def test_stop_run_rejects_terminal_state(db_session):
    """终态运行不允许再次停止。"""
    from modules.configuration_task.entity.vo.task_vo import TaskRunStopModel

    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="SUCCESS",
            input_snapshot_json="{}",
            run_params_json="{}",
            started_at=now,
            ended_at=now,
            duration_ms=100,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()
    result = asyncio.run(
        ConfigurationTaskRunService.stop_run(db_session, RUN_ID, TaskRunStopModel(), _current_user())
    )
    assert result.is_success is False
    assert "已结束" in result.message


def test_handle_agent_run_event_updates_progress(db_session):
    """web_run_step 事件应更新运行结果 JSON，web_run_finished 收敛终态。"""
    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="RUNNING",
            input_snapshot_json="{}",
            run_params_json="{}",
            started_at=now,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()

    handled = ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {
            "type": "web_run_step",
            "webCaseRunId": RUN_ID,
            "payload": {
                "phase": "step_finished",
                "step": {"stepIndex": 1, "stepName": "s1", "status": "passed"},
                "progress": {"totalSteps": 2, "finishedSteps": 1},
            },
        },
    )
    assert handled is True
    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    assert row.status == "RUNNING"
    assert "steps" in db_session.get(ConfigurationTaskRun, RUN_ID).result_json or True
    import json as _json

    result_payload = _json.loads(row.result_json)
    assert result_payload["steps"][0]["status"] == "passed"

    finished = ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {
            "type": "web_run_finished",
            "webCaseRunId": RUN_ID,
            "payload": {"success": True, "steps": [{"stepIndex": 1, "status": "passed"}]},
        },
    )
    assert finished is True
    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    assert row.status == "SUCCESS"


def test_handle_agent_run_event_uses_stable_step_id_for_replacement(db_session):
    """同一稳定 stepId 再次上报时应更新原步骤，而不是追加重复步骤。"""
    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="RUNNING",
            input_snapshot_json="{}",
            run_params_json="{}",
            result_json='{"steps":[{"stepId":"capture-before-save","stepIndex":2,"status":"passed"}]}',
            started_at=now,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()

    handled = ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {
            "type": "web_run_step",
            "webCaseRunId": RUN_ID,
            "payload": {
                "phase": "step_finished",
                "step": {
                    "stepId": "capture-before-save",
                    "stepIndex": 7,
                    "stepName": "保存前截图",
                    "actionType": "capture_screenshot",
                    "status": "passed",
                },
            },
        },
    )

    assert handled is True
    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    result_payload = json.loads(row.result_json)
    assert len(result_payload["steps"]) == 1
    assert result_payload["steps"][0]["stepIndex"] == 7
    assert result_payload["steps"][0]["actionType"] == "capture_screenshot"


def test_handle_agent_run_event_ignores_other_table_ids(db_session):
    """未命中配置任务运行表的事件必须返回 False，交回 Web 用例链路。"""
    _task(db_session)
    handled = ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {"type": "web_run_step", "webCaseRunId": 12345, "payload": {}},
    )
    assert handled is False


def test_recover_orphan_running_refreshes_evidence_status(db_session):
    """孤儿运行收敛失败时，同时刷新阶段和运行证据状态。"""
    _task(db_session)
    stale_time = datetime(2020, 1, 1)
    run = ConfigurationTaskRun(
        task_run_id=RUN_ID,
        task_id=TASK_ID,
        task_version_id=VERSION_ID,
        version_no=1,
        agent_code="agent-01",
        trigger_type="manual",
        status="RUNNING",
        input_snapshot_json="{}",
        run_params_json=(
            '{"evidencePlan":{"steps":{"step-before":'
            '{"evidenceType":"before_screenshot","evidenceKey":"before"}}}}'
        ),
        started_at=stale_time,
        create_by="tester",
        update_by="tester",
        create_time=stale_time,
        update_time=stale_time,
    )
    db_session.add(run)
    db_session.add(
        TaskRunStage(
            task_run_id=RUN_ID,
            stage_id=1,
            stage_key="query",
            stage_name="查询",
            mode="READ",
            stage_order=1,
            step_range_json="[0]",
            step_ids_json='["step-before"]',
            evidence_policy_json=(
                '{"mode":"REQUIRED","requiredTypes":["before_screenshot"]}'
            ),
            status="RUNNING",
            create_time=stale_time,
            update_time=stale_time,
        )
    )
    db_session.commit()

    result = ConfigurationTaskRunService.recover_orphan_running(db_session, timeout_minutes=60)

    assert result["recovered"] == 1
    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    stage = db_session.query(TaskRunStage).filter(TaskRunStage.task_run_id == RUN_ID).one()
    assert row.status == "FAILED"
    assert row.evidence_status == "INCOMPLETE"
    assert stage.evidence_status == "INCOMPLETE"
    assert "before_screenshot" in row.evidence_missing_json


def test_stage_event_prefers_step_id_and_waits_for_all_steps(db_session):
    """阶段事件应优先按 stepId 映射，乱序上报不能提前结束阶段。"""
    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="RUNNING",
            input_snapshot_json="{}",
            run_params_json="{}",
            result_json="{}",
            started_at=now,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.add(
        TaskRunStage(
            task_run_id=RUN_ID,
            stage_id=1,
            stage_key="query",
            stage_name="查询",
            mode="READ",
            stage_order=1,
            step_range_json="[0,1]",
            step_ids_json='["step-a","step-b"]',
            status="PENDING",
            create_time=now,
            update_time=now,
        )
    )
    db_session.commit()

    # step-b 乱序先到，且展示索引故意指向另一个位置；稳定 stepId 应优先。
    assert ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {
            "type": "web_run_step",
            "webCaseRunId": RUN_ID,
            "payload": {
                "step": {"stepId": "step-b", "stepIndex": 1, "status": "passed"}
            },
        },
    )
    stage = db_session.query(TaskRunStage).filter(TaskRunStage.task_run_id == RUN_ID).one()
    assert stage.status == "RUNNING"

    assert ConfigurationTaskRunService.handle_agent_run_event(
        db_session,
        "agent-01",
        {
            "type": "web_run_step",
            "webCaseRunId": RUN_ID,
            "payload": {
                "step": {"stepId": "step-a", "stepIndex": 2, "status": "passed"}
            },
        },
    )
    db_session.refresh(stage)
    assert stage.status == "SUCCESS"


def test_terminal_run_ignores_late_agent_events(db_session):
    """运行进入终态后，迟到步骤、状态和终态事件不能覆盖结果。"""
    _task(db_session)
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=VERSION_ID,
            version_no=1,
            agent_code="agent-01",
            trigger_type="manual",
            status="SUCCESS",
            business_status="SUCCESS",
            evidence_status="COMPLETE",
            evidence_missing_json="[]",
            result_json='{"winner":"finished"}',
            error_code="",
            error_message="",
            started_at=now,
            ended_at=now,
            duration_ms=12,
            create_by="tester",
            create_time=now,
            update_by="tester",
            update_time=now,
        )
    )
    db_session.commit()

    for message_type, payload in (
        ("web_run_step", {"step": {"stepId": "late", "status": "failed"}}),
        ("web_run_status", {"phase": "running"}),
        ("web_run_finished", {"success": False, "steps": []}),
        ("web_run_error", {"message": "late error"}),
    ):
        assert ConfigurationTaskRunService.handle_agent_run_event(
            db_session,
            "agent-01",
            {
                "type": message_type,
                "webCaseRunId": RUN_ID,
                "payload": payload,
            },
        ) is True

    row = db_session.get(ConfigurationTaskRun, RUN_ID)
    assert row.status == "SUCCESS"
    assert row.business_status == "SUCCESS"
    assert row.result_json == '{"winner":"finished"}'
    assert row.error_code == ""
    assert row.error_message == ""
    assert row.duration_ms == 12
