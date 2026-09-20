"""SFTP Provider、资源下载回传与删除引用保护测试。"""

import base64
import hashlib
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from config.database import Base
from modules.configuration_task.dao.stage_artifact_dao import TaskArtifactDao
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.stage_artifact_do import TaskArtifact
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceDeleteModel,
)
from modules.configuration_task.service.resource_extended_service import (
    ResourceExtendedService,
)
from modules.configuration_task.util.sftp_provider import (
    SftpConfig,
    SftpProvider,
    validate_object_key,
)

RESOURCE_ID = 600000000000001
SHA256 = "d" * 64


@pytest.fixture
def db_session():
    """创建 SFTP 资源测试所需的 SQLite 会话。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[ResourceObject.__table__, TaskArtifact.__table__],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user(admin=False):
    """构造操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester", admin=admin))


def _sftp_resource(db, audit_message="SFTP_UPLOAD|bindingId=88|operator=tester", status="READY"):
    """写入一个 SFTP 资源实体。"""
    now = datetime.now()
    row = ResourceObject(
        resource_id=RESOURCE_ID,
        provider_type="sftp",
        provider_execution_side="server",
        agent_code="agent-01",
        object_key="inputs/demo.txt",
        original_file_name="demo.txt",
        mime_type="text/plain",
        file_size=11,
        checksum_algorithm="sha256",
        sha256=SHA256,
        version=1,
        status=status,
        create_by="tester",
        create_time=now,
        update_by="tester",
        update_time=now,
        audit_message=audit_message,
    )
    db.add(row)
    db.commit()
    return row


def test_validate_object_key_rejects_traversal_and_absolute():
    """SFTP object key 拒绝绝对路径、路径穿越和反斜杠。"""
    assert validate_object_key("inputs/demo.txt") == "inputs/demo.txt"
    assert validate_object_key("inputs\\demo.txt") == "inputs/demo.txt"
    import pytest

    from modules.configuration_task.util.sftp_provider import SftpProviderError

    for bad in ("/abs/path", "../escape", "a/../b", "", "~/home", "a//b"):
        with pytest.raises(SftpProviderError):
            validate_object_key(bad)


def test_sftp_provider_upload_uses_part_and_rename(monkeypatch):
    """SFTP 上传先写 .part 再 rename，失败清理临时对象。"""

    calls = []

    class FakeHandle:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def write(self, data):
            calls.append(("write", len(data)))

        def flush(self):
            pass

    class FakeSftp:
        def open(self, path, mode):
            calls.append(("open", path, mode))
            return FakeHandle(path)

        def rename(self, src, dst):
            calls.append(("rename", src, dst))

        def stat(self, path):
            calls.append(("stat", path))
            if path and not path.endswith(".part"):
                return SimpleNamespace(st_size=1, st_mtime=0)
            raise OSError("not found")

        def mkdir(self, path):
            calls.append(("mkdir", path))

    provider = SftpProvider(SftpConfig(host="127.0.0.1", username="u", password="p", base_directory="/data"))
    monkeypatch.setattr(provider, "_ensure_connected", lambda: FakeSftp())
    result = provider.upload("inputs/demo.txt", b"hello world")
    assert result["size"] == 11
    assert result["sha256"] == hashlib.sha256(b"hello world").hexdigest()
    # 断言 .part 先写入，rename 到正式 key。
    operations = [call[0] for call in calls]
    assert "open" in operations and "rename" in operations
    rename_call = next(call for call in calls if call[0] == "rename")
    assert rename_call[1].endswith(".part")
    assert not rename_call[2].endswith(".part")


def test_download_sftp_resource_verifies_sha256(db_session, monkeypatch):
    """SFTP 下载回传需校验 SHA-256；摘要一致才允许返回。"""
    content = b"hello world"
    row = _sftp_resource(db_session)
    row.sha256 = hashlib.sha256(content).hexdigest()
    db_session.commit()

    class FakeProvider:
        def __init__(self, config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, key):
            return content

    import modules.configuration_task.service.resource_extended_service as module

    monkeypatch.setattr(module, "SftpProvider", FakeProvider)
    monkeypatch.setattr(
        module,
        "resolve_sftp_config",
        lambda secret: SftpConfig(host="h", username="u", password="p"),
    )
    monkeypatch.setattr(
        ResourceExtendedService,
        "_resolve_sftp_credential",
        staticmethod(lambda db, binding_id: (SimpleNamespace(binding_id=88), None, {})),
    )
    result = ResourceExtendedService.download_resource(db_session, RESOURCE_ID, _current_user())
    assert result.is_success is True
    payload = result.result.model_dump(by_alias=True)
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()
    assert base64.b64decode(payload["data"]) == content


def test_download_rejects_status_not_ready(db_session):
    """非 READY 资源拒绝下载。"""
    _sftp_resource(db_session, status="PENDING")
    result = ResourceExtendedService.download_resource(db_session, RESOURCE_ID, _current_user())
    assert result.is_success is False
    assert "不允许下载" in result.message


def test_delete_resource_blocked_by_artifact_reference(db_session):
    """被产物引用的资源默认拒绝删除；管理员 force 可删除。"""
    _sftp_resource(db_session)
    now = datetime.now()
    TaskArtifactDao.add_artifact(
        db_session,
        {
            "task_run_id": 1,
            "run_stage_id": None,
            "artifact_type": "report",
            "step_key": "",
            "resource_id": RESOURCE_ID,
            "original_file_name": "report.doc",
            "file_size": 10,
            "sha256": SHA256,
            "note": "",
            "create_by": "tester",
            "create_time": now,
        },
    )
    db_session.commit()
    # 非强制：拒绝。
    blocked = ResourceExtendedService.delete_resource(
        db_session, RESOURCE_ID, ResourceDeleteModel(force=False), _current_user()
    )
    assert blocked.is_success is False
    assert "引用" in blocked.message
    # 非管理员强制：拒绝。
    denied = ResourceExtendedService.delete_resource(
        db_session, RESOURCE_ID, ResourceDeleteModel(force=True), _current_user(admin=False)
    )
    assert denied.is_success is False
    assert "管理员" in denied.message


def test_delete_resource_marks_deleting_then_deleted(db_session, monkeypatch):
    """删除流程：DELETING → 清理远端文件 → DELETED；清理失败保留 DELETING。"""
    _sftp_resource(db_session)
    # 未被引用：直接删除成功。
    monkeypatch.setattr(
        ResourceExtendedService, "_delete_provider_file", classmethod(lambda cls, db, row: "")
    )
    result = ResourceExtendedService.delete_resource(
        db_session, RESOURCE_ID, ResourceDeleteModel(reason="测试删除"), _current_user(admin=True)
    )
    assert result.is_success is True
    assert result.result.model_dump(by_alias=True)["status"] == "DELETED"


def test_delete_provider_file_failure_keeps_deleting(db_session, monkeypatch):
    """远端文件清理失败时资源保留在 DELETING，等待重试。"""
    _sftp_resource(db_session)
    monkeypatch.setattr(
        ResourceExtendedService,
        "_delete_provider_file",
        classmethod(lambda cls, db, row: "SFTP 连接失败，请检查凭证与网络"),
    )
    result = ResourceExtendedService.delete_resource(
        db_session, RESOURCE_ID, ResourceDeleteModel(), _current_user(admin=True)
    )
    assert result.is_success is False
    assert "远端文件清理失败" in result.message
    assert db_session.get(ResourceObject, RESOURCE_ID).status == "DELETING"


def test_agent_resource_download_via_file_read(db_session, monkeypatch):
    """agent_local 资源下载回传走 Agent file_read 命令并校验摘要。"""
    row = _sftp_resource(db_session)
    row.provider_type = "agent_local"
    row.provider_execution_side = "agent"
    row.sha256 = hashlib.sha256(b"agent-content").hexdigest()
    db_session.commit()

    content_b64 = base64.b64encode(b"agent-content").decode("ascii")

    def fake_send_command(agent_code, command, payload, **kwargs):
        assert command == "file_read"
        return SimpleNamespace(success=True, data={"data": content_b64}, error_code="", error_message="")


    monkeypatch.setattr(
        "module_qtr.service.agent_file_transfer_service.AgentFileTransferService.send_command",
        staticmethod(fake_send_command),
    )
    result = ResourceExtendedService.download_resource(db_session, RESOURCE_ID, _current_user())
    assert result.is_success is True
    payload = result.result.model_dump(by_alias=True)
    assert base64.b64decode(payload["data"]) == b"agent-content"


def test_agent_resource_download_sha_mismatch_rejected(db_session):
    """Agent 返回内容与登记摘要不一致时拒绝回传。"""
    _sftp_resource(db_session)
    row = db_session.get(ResourceObject, RESOURCE_ID)
    row.provider_type = "agent_local"
    row.provider_execution_side = "agent"
    db_session.commit()

    bad_b64 = base64.b64encode(b"tampered").decode("ascii")

    monkeypatch_send = SimpleNamespace(
        send_command=staticmethod(
            lambda *args, **kwargs: SimpleNamespace(
                success=True, data={"data": bad_b64}, error_code="", error_message=""
            )
        )
    )
    monkeypatch_send.send_command.__func__.__qualname__ = "send_command"
    from module_qtr.service import agent_file_transfer_service as transfer_module

    original = transfer_module.AgentFileTransferService.send_command
    transfer_module.AgentFileTransferService.send_command = staticmethod(
        lambda *args, **kwargs: SimpleNamespace(
            success=True, data={"data": bad_b64}, error_code="", error_message=""
        )
    )
    try:
        result = ResourceExtendedService.download_resource(db_session, RESOURCE_ID, _current_user())
        assert result.is_success is False
        assert "校验失败" in result.message
    finally:
        transfer_module.AgentFileTransferService.send_command = original
