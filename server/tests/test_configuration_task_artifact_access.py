"""配置任务运行产物受控访问与 metadata-only 状态测试。"""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import Base
from modules.configuration_task.entity.do.artifact_access_audit_do import (
    ConfigurationTaskArtifactAccessAudit,
)
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.stage_artifact_do import TaskArtifact
from modules.configuration_task.entity.do.task_do import ConfigurationTask
from modules.configuration_task.entity.do.task_run_do import ConfigurationTaskRun
from modules.configuration_task.entity.vo.task_vo import AgentStepScreenshotModel
from modules.configuration_task.service.artifact_access_service import (
    ConfigurationTaskArtifactAccessService,
)
from modules.configuration_task.service.artifact_service import ConfigurationTaskArtifactService
from modules.configuration_task.service.resource_extended_service import ResourceExtendedService

TASK_ID = 810000000000001
RUN_ID = 810000000000002
ARTIFACT_ID = 810000000000003
RESOURCE_ID = 810000000000004
CONTENT = b"artifact-content"
CONTENT_SHA256 = hashlib.sha256(CONTENT).hexdigest()


@pytest.fixture
def db_session():
    """创建产物访问测试所需的 SQLite 会话。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ConfigurationTask.__table__,
            ConfigurationTaskRun.__table__,
            ResourceObject.__table__,
            TaskArtifact.__table__,
            ConfigurationTaskArtifactAccessAudit.__table__,
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user(name: str, admin: bool = False):
    """构造访问操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name=name, admin=admin))


def _seed_artifact(
    db: Session,
    *,
    task_owner: str = "task-owner",
    run_owner: str = "run-owner",
    artifact_owner: str = "artifact-owner",
    resource_owner: str = "resource-owner",
    artifact_id: int = ARTIFACT_ID,
    run_id: int = RUN_ID,
    resource_id: int = RESOURCE_ID,
    provider_type: str = "agent_local",
    provider_execution_side: str = "agent",
    object_key: str = "resources/agent-local-demo",
    mime_type: str = "text/plain",
    file_name: str = "result.txt",
    file_size: int = len(CONTENT),
    sha256: str = CONTENT_SHA256,
    resource_status: str = "READY",
    availability_status: str = "ONLINE",
    expires_at: datetime | None = None,
):
    """写入一组可独立修改归属和元数据的任务、运行、资源和产物。"""
    now = datetime.now()
    db.add(
        ConfigurationTask(
            task_id=TASK_ID,
            task_name="产物访问任务",
            agent_code="agent-01",
            status="ACTIVE",
            create_by=task_owner,
            create_time=now,
            update_by=task_owner,
            update_time=now,
        )
    )
    db.add(
        ConfigurationTaskRun(
            task_run_id=run_id,
            task_id=TASK_ID,
            task_version_id=1,
            version_no=1,
            agent_code="agent-01",
            status="SUCCESS",
            create_by=run_owner,
            create_time=now,
            update_by=run_owner,
            update_time=now,
        )
    )
    db.add(
        ResourceObject(
            resource_id=resource_id,
            provider_type=provider_type,
            provider_execution_side=provider_execution_side,
            agent_code="agent-01",
            object_key=object_key,
            original_file_name=file_name,
            mime_type=mime_type,
            file_size=file_size,
            checksum_algorithm="sha256",
            sha256=sha256,
            version=1,
            status=resource_status,
            expires_at=expires_at,
            create_by=resource_owner,
            create_time=now,
            update_by=resource_owner,
            update_time=now,
        )
    )
    db.add(
        TaskArtifact(
            artifact_id=artifact_id,
            task_run_id=run_id,
            run_stage_id=None,
            artifact_type="execution_log",
            step_key="",
            step_id="",
            evidence_type="execution_log",
            evidence_key="execution-log",
            sequence_no=1,
            availability_status=availability_status,
            provider_type=provider_type,
            agent_code="agent-01",
            object_key=object_key,
            mime_type=mime_type,
            resource_id=resource_id,
            original_file_name=file_name,
            file_size=file_size,
            sha256=sha256,
            note="测试产物",
            create_by=artifact_owner,
            create_time=now,
        )
    )
    db.commit()


def _patch_read_content(monkeypatch, content: bytes = CONTENT):
    """隔离正文读取 Provider，只验证访问服务的后置校验。"""
    monkeypatch.setattr(
        ResourceExtendedService,
        "read_resource_content",
        staticmethod(lambda db, row, operator: content),
    )


def test_artifact_access_allows_task_run_artifact_and_admin_owners(db_session, monkeypatch):
    """任务、运行、产物和资源任一归属者以及管理员均可访问。"""
    _seed_artifact(db_session)
    _patch_read_content(monkeypatch)

    for operator in ("task-owner", "run-owner", "artifact-owner", "resource-owner"):
        result = ConfigurationTaskArtifactAccessService.access_artifact(
            db_session, ARTIFACT_ID, _current_user(operator), "download"
        )
        assert result.is_success is True
        assert result.result is not None
        assert result.result.disposition == "attachment"

    admin_result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("admin", admin=True), "download"
    )
    assert admin_result.is_success is True
    assert db_session.query(ConfigurationTaskArtifactAccessAudit).count() == 5


def test_artifact_access_denies_unrelated_user_and_records_audit(db_session, monkeypatch):
    """无关用户不能仅凭 artifact_id 读取正文，失败也要写审计。"""
    _seed_artifact(db_session)
    _patch_read_content(monkeypatch)

    result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("unrelated"), "preview"
    )

    assert result.is_success is False
    assert result.error_code == "ACCESS_DENIED"
    assert result.result is None
    audit = db_session.query(ConfigurationTaskArtifactAccessAudit).one()
    assert audit.action == "preview"
    assert audit.success is False
    assert audit.error_code == "ACCESS_DENIED"
    assert "unrelated" == audit.operator


def test_artifact_access_unknown_artifact_records_failure_audit(db_session):
    """未知产物返回稳定错误码，并保留可追踪的失败审计。"""
    result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, 899999999999999, _current_user("tester"), "download"
    )

    assert result.is_success is False
    assert result.error_code == "ARTIFACT_NOT_FOUND"
    audit = db_session.query(ConfigurationTaskArtifactAccessAudit).one()
    assert audit.artifact_id == 899999999999999
    assert audit.task_run_id is None
    assert audit.resource_id is None


def test_artifact_access_rejects_missing_run_and_resource(db_session):
    """运行不存在或资源不存在时不能继续读取 Provider。"""
    now = datetime.now()
    db_session.add(
        ConfigurationTask(
            task_id=TASK_ID,
            task_name="产物访问任务",
            agent_code="agent-01",
            status="ACTIVE",
            create_by="owner",
            create_time=now,
            update_by="owner",
            update_time=now,
        )
    )
    db_session.add(
        TaskArtifact(
            artifact_id=ARTIFACT_ID,
            task_run_id=999999999999998,
            artifact_type="execution_log",
            evidence_type="execution_log",
            evidence_key="missing-run",
            provider_type="agent_local",
            agent_code="agent-01",
            object_key="resources/missing",
            mime_type="text/plain",
            resource_id=RESOURCE_ID,
            original_file_name="missing.txt",
            file_size=1,
            sha256="a" * 64,
            create_by="owner",
            create_time=now,
        )
    )
    db_session.commit()

    missing_run = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("owner"), "download"
    )
    assert missing_run.error_code == "RUN_NOT_FOUND"

    db_session.query(TaskArtifact).delete()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=1,
            version_no=1,
            agent_code="agent-01",
            status="SUCCESS",
            create_by="owner",
            create_time=now,
            update_by="owner",
            update_time=now,
        )
    )
    db_session.add(
        TaskArtifact(
            artifact_id=ARTIFACT_ID,
            task_run_id=RUN_ID,
            artifact_type="execution_log",
            evidence_type="execution_log",
            evidence_key="missing-resource",
            availability_status="ONLINE",
            provider_type="agent_local",
            agent_code="agent-01",
            object_key="resources/missing",
            mime_type="text/plain",
            resource_id=RESOURCE_ID,
            original_file_name="missing.txt",
            file_size=1,
            sha256="a" * 64,
            create_by="owner",
            create_time=now,
        )
    )
    db_session.commit()

    missing_resource = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("owner"), "download"
    )
    assert missing_resource.error_code == "RESOURCE_NOT_FOUND"


def test_artifact_access_rejects_inconsistent_metadata(db_session):
    """产物和资源的大小、摘要、MIME、Agent、定位键不一致均拒绝。"""
    mismatch_cases = (
        ("file_size", "SIZE_MISMATCH"),
        ("sha256", "CHECKSUM_MISMATCH"),
        ("mime_type", "METADATA_MISMATCH"),
        ("agent_code", "METADATA_MISMATCH"),
        ("object_key", "METADATA_MISMATCH"),
    )
    for index, (field, expected_code) in enumerate(mismatch_cases, start=1):
        db_session.rollback()
        db_session.query(TaskArtifact).delete()
        db_session.query(ResourceObject).delete()
        db_session.query(ConfigurationTaskRun).delete()
        db_session.query(ConfigurationTask).delete()
        db_session.commit()
        _seed_artifact(
            db_session,
            artifact_id=ARTIFACT_ID + index,
            run_id=RUN_ID + index,
            resource_id=RESOURCE_ID + index,
        )
        artifact = db_session.get(TaskArtifact, ARTIFACT_ID + index)
        if field == "file_size":
            artifact.file_size += 1
        elif field == "sha256":
            artifact.sha256 = "b" * 64
        elif field == "mime_type":
            artifact.mime_type = "application/json"
        elif field == "agent_code":
            artifact.agent_code = "agent-other"
        else:
            artifact.object_key = "resources/other"
        db_session.commit()

        result = ConfigurationTaskArtifactAccessService.access_artifact(
            db_session, ARTIFACT_ID + index, _current_user("task-owner"), "download"
        )
        assert result.error_code == expected_code


def test_preview_requires_safe_mime_and_download_sanitizes_file_name(db_session, monkeypatch):
    """预览只允许安全 MIME，下载文件名不得携带路径或控制字符。"""
    _seed_artifact(db_session, mime_type="application/pdf", file_name="../report<>.pdf")
    _patch_read_content(monkeypatch)

    preview = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "preview"
    )
    assert preview.is_success is False
    assert preview.error_code == "PREVIEW_UNSUPPORTED"

    download = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert download.is_success is True
    assert download.result is not None
    assert download.result.file_name == "report_.pdf"
    assert download.result.disposition == "attachment"


def test_artifact_access_rejects_unavailable_expired_and_read_checksum_mismatch(
    db_session, monkeypatch
):
    """不可用、过期和读取后摘要不一致均拒绝正文。"""
    _seed_artifact(db_session, resource_status="FAILED", availability_status="AGENT_OFFLINE")
    unavailable = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert unavailable.error_code == "ARTIFACT_UNAVAILABLE"

    db_session.query(TaskArtifact).delete()
    db_session.query(ResourceObject).delete()
    db_session.query(ConfigurationTaskRun).delete()
    db_session.query(ConfigurationTask).delete()
    db_session.commit()
    _seed_artifact(db_session, expires_at=datetime.now() - timedelta(minutes=1))
    expired = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert expired.error_code == "RESOURCE_EXPIRED"

    db_session.query(TaskArtifact).delete()
    db_session.query(ResourceObject).delete()
    db_session.query(ConfigurationTaskRun).delete()
    db_session.query(ConfigurationTask).delete()
    db_session.commit()
    _seed_artifact(db_session)
    _patch_read_content(monkeypatch, b"tampered")
    mismatch = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert mismatch.error_code == "CHECKSUM_MISMATCH"
    assert mismatch.result is None


def test_report_provider_reads_fixed_directory_without_agent(monkeypatch, db_session, tmp_path: Path):
    """服务端报告只能从固定目录读取，不应调用 Agent。"""
    import modules.configuration_task.service.resource_extended_service as resource_module

    report_hash = "a" * 16
    report_path = tmp_path / f"{RUN_ID}_{report_hash}.doc"
    report_path.write_bytes(CONTENT)
    monkeypatch.setattr(resource_module, "RUN_REPORTS_DIR", tmp_path)
    monkeypatch.setattr(
        resource_module.AgentFileTransferService,
        "send_command",
        staticmethod(lambda *args, **kwargs: pytest.fail("服务端报告不应调用 Agent")),
    )
    _seed_artifact(
        db_session,
        provider_type="report",
        provider_execution_side="server",
        object_key=f"reports/{RUN_ID}/{report_hash}",
        file_name="report.doc",
    )

    result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert result.is_success is True
    assert result.result is not None
    assert result.result.content == CONTENT


def test_sftp_provider_is_selected_before_server_side_report(monkeypatch, db_session):
    """SFTP 虽然在服务端执行，也必须走 SFTP Provider 而不是报告目录。"""
    import modules.configuration_task.service.resource_extended_service as resource_module

    calls = []

    class FakeProvider:
        def __init__(self, config):
            calls.append(("init", config))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, object_key):
            calls.append(("download", object_key))
            return CONTENT

    monkeypatch.setattr(resource_module, "SftpProvider", FakeProvider)
    monkeypatch.setattr(
        resource_module,
        "resolve_sftp_config",
        lambda secret: SimpleNamespace(secret=secret),
    )
    monkeypatch.setattr(
        ResourceExtendedService,
        "_resolve_sftp_credential",
        staticmethod(lambda db, binding_id: (SimpleNamespace(binding_id=88), None, {})),
    )
    _seed_artifact(
        db_session,
        provider_type="sftp",
        provider_execution_side="server",
        object_key="inputs/demo.txt",
        file_name="demo.txt",
    )
    resource = db_session.get(ResourceObject, RESOURCE_ID)
    resource.audit_message = "SFTP_UPLOAD|bindingId=88|operator=task-owner"
    db_session.commit()

    result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert result.is_success is True
    assert ("download", "inputs/demo.txt") in calls


def test_agent_provider_sends_expected_size_and_sha256(monkeypatch, db_session):
    """Agent file_read 使用受控本地 ID，并携带 expected size/hash。"""
    calls = []

    def fake_send_command(agent_code, command, payload, **kwargs):
        calls.append((agent_code, command, payload, kwargs))
        return SimpleNamespace(
            success=True,
            data={"data": "YXJ0aWZhY3QtY29udGVudA=="},
            error_code="",
            error_message="",
        )

    monkeypatch.setattr(
        "module_qtr.service.agent_file_transfer_service.AgentFileTransferService.send_command",
        staticmethod(fake_send_command),
    )
    _seed_artifact(db_session)

    result = ConfigurationTaskArtifactAccessService.access_artifact(
        db_session, ARTIFACT_ID, _current_user("task-owner"), "download"
    )
    assert result.is_success is True
    assert calls[0][1] == "file_read"
    assert calls[0][2] == {
        "resource_id": "agent-local-demo",
        "expected_size": len(CONTENT),
        "expected_sha256": CONTENT_SHA256,
    }


@pytest.mark.parametrize(
    ("error_code", "expected_availability"),
    [
        ("AGENT_OFFLINE", "AGENT_OFFLINE"),
        ("RESOURCE_NOT_FOUND", "NOT_FOUND"),
        ("RESOURCE_EXPIRED", "NOT_FOUND"),
        ("CHECKSUM_MISMATCH", "CHECKSUM_MISMATCH"),
        ("SIZE_MISMATCH", "CHECKSUM_MISMATCH"),
    ],
)
def test_metadata_only_file_stat_failure_states(
    db_session, monkeypatch, error_code: str, expected_availability: str
):
    """metadata-only file_stat 失败时资源不可 READY，产物保留明确不可用状态。"""
    calls = []

    def fake_send_command(agent_code, command, payload, **kwargs):
        calls.append((agent_code, command, payload, kwargs))
        return SimpleNamespace(
            success=False,
            data={},
            error_code=error_code,
            error_message=f"模拟 {error_code}",
        )

    monkeypatch.setattr(
        "modules.configuration_task.service.artifact_service.AgentFileTransferService.send_command",
        staticmethod(fake_send_command),
    )
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=1,
            version_no=1,
            agent_code="agent-01",
            status="RUNNING",
            create_by="owner",
            create_time=now,
            update_by="owner",
            update_time=now,
        )
    )
    db_session.commit()
    model = AgentStepScreenshotModel(
        taskRunId=str(RUN_ID),
        artifactType="step_screenshot",
        providerType="agent_local",
        agentCode="agent-01",
        objectKey="resources/agent-local-demo",
        fileName="capture.png",
        mimeType="image/png",
        fileSize=len(CONTENT),
        sha256=CONTENT_SHA256,
    )

    result = ConfigurationTaskArtifactService.register_agent_screenshot(
        db_session, model, _current_user("owner")
    )

    assert result.is_success is True
    assert calls[0][1] == "file_stat"
    assert calls[0][2]["resource_id"] == "agent-local-demo"
    assert calls[0][2]["expected_size"] == len(CONTENT)
    assert calls[0][2]["expected_sha256"] == CONTENT_SHA256
    resource = db_session.query(ResourceObject).one()
    artifact = db_session.query(TaskArtifact).one()
    assert resource.status == "FAILED"
    assert resource.error_code == error_code
    assert artifact.availability_status == expected_availability


def test_metadata_only_file_stat_success_marks_ready_and_online(db_session, monkeypatch):
    """file_stat 返回真实匹配摘要时才允许 READY/ONLINE。"""
    calls = []

    def fake_send_command(agent_code, command, payload, **kwargs):
        calls.append((agent_code, command, payload, kwargs))
        return SimpleNamespace(
            success=True,
            data={"size": len(CONTENT), "sha256": CONTENT_SHA256},
            error_code="",
            error_message="",
        )

    monkeypatch.setattr(
        "modules.configuration_task.service.artifact_service.AgentFileTransferService.send_command",
        staticmethod(fake_send_command),
    )
    now = datetime.now()
    db_session.add(
        ConfigurationTaskRun(
            task_run_id=RUN_ID,
            task_id=TASK_ID,
            task_version_id=1,
            version_no=1,
            agent_code="agent-01",
            status="RUNNING",
            create_by="owner",
            create_time=now,
            update_by="owner",
            update_time=now,
        )
    )
    db_session.commit()
    model = AgentStepScreenshotModel(
        taskRunId=str(RUN_ID),
        artifactType="step_screenshot",
        providerType="agent_local",
        agentCode="agent-01",
        objectKey="resources/agent-local-demo",
        fileName="capture.png",
        mimeType="image/png",
        fileSize=len(CONTENT),
        sha256=CONTENT_SHA256,
    )

    result = ConfigurationTaskArtifactService.register_agent_screenshot(
        db_session, model, _current_user("owner")
    )

    assert result.is_success is True
    assert calls[0][1] == "file_stat"
    resource = db_session.query(ResourceObject).one()
    artifact = db_session.query(TaskArtifact).one()
    assert resource.status == "READY"
    assert artifact.availability_status == "ONLINE"
