"""配置任务资源传输状态机测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.database import Base
from module_qtr.service.agent_file_transfer_service import AgentFileCommandResult
from module_qtr.service.agent_service import agent_sessions, agents
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.do.resource_transfer_do import ResourceTransfer
from modules.configuration_task.entity.vo.resource_vo import (
    ResourceTransferBeginModel,
    ResourceTransferChunkModel,
    ResourceTransferCommitModel,
)
from modules.configuration_task.service.resource_transfer_service import ResourceTransferService

RESOURCE_ID = 900000000000001
SHA256 = "a" * 64


@pytest.fixture
def db_session():
    """创建传输状态机测试所需的 SQLite 会话。"""
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[ResourceObject.__table__, ResourceTransfer.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user():
    """构造非管理员资源操作者。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester", admin=False))


def _resource(status="PENDING", expires_at=None):
    """构造测试资源实体。"""
    now = datetime.now()
    return ResourceObject(
        resource_id=RESOURCE_ID,
        provider_type="agent_local",
        provider_execution_side="agent",
        agent_code="agent-01",
        object_key="inputs/demo.txt",
        original_file_name="demo.txt",
        mime_type="text/plain",
        file_size=3,
        checksum_algorithm="sha256",
        sha256=SHA256,
        version=1,
        status=status,
        expires_at=expires_at,
        create_by="tester",
        create_time=now,
        update_by="tester",
        update_time=now,
    )


def test_transfer_moves_to_ready_after_agent_commit(db_session, monkeypatch):
    """Agent begin、chunk、commit 成功后资源只能由 commit 置为 READY。"""
    db_session.add(_resource())
    db_session.commit()
    agent_sessions["agent-01"] = "session-1"
    agents["agent-01"] = object()
    monkeypatch.setattr(ResourceTransferService, "_agent_online", staticmethod(lambda db, code: True))

    def fake_send(agent_code, command, payload, **kwargs):
        if command == "file_chunk":
            return AgentFileCommandResult(True, {"received": 3, "idempotent": False})
        if command == "file_publish_commit":
            return AgentFileCommandResult(True, {"size": 3, "sha256": SHA256})
        return AgentFileCommandResult(True, {"transfer_id": payload["transfer_id"]})

    monkeypatch.setattr(
        "modules.configuration_task.service.resource_transfer_service.AgentFileTransferService.send_command",
        fake_send,
    )
    try:
        begin = ResourceTransferService.begin(
            db_session, RESOURCE_ID, ResourceTransferBeginModel(transferId="transfer-1"), _current_user()
        )
        assert begin.is_success is True
        assert begin.result.status == "UPLOADING"

        chunk = ResourceTransferChunkModel(
            index=0,
            offset=0,
            totalBytes=3,
            chunkBytes=3,
            chunkSha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            data="YWJj",
        )
        chunk_result = ResourceTransferService.chunk(
            db_session, RESOURCE_ID, "transfer-1", chunk, _current_user()
        )
        assert chunk_result.is_success is True
        assert chunk_result.result.received_bytes == 3

        commit = ResourceTransferService.commit(
            db_session, RESOURCE_ID, "transfer-1", ResourceTransferCommitModel(), _current_user()
        )
        assert commit.is_success is True
        assert commit.result.status == "COMPLETED"
        assert db_session.get(ResourceObject, RESOURCE_ID).status == "READY"
        assert db_session.get(ResourceTransfer, "transfer-1").status == "COMPLETED"
    finally:
        agents.pop("agent-01", None)
        agent_sessions.pop("agent-01", None)


def test_transfer_commit_metadata_mismatch_marks_failed(db_session, monkeypatch):
    """Agent commit 返回的摘要不匹配时，资源和传输都进入 FAILED。"""
    db_session.add(_resource())
    db_session.commit()
    agent_sessions["agent-01"] = "session-1"
    agents["agent-01"] = object()
    monkeypatch.setattr(ResourceTransferService, "_agent_online", staticmethod(lambda db, code: True))
    monkeypatch.setattr(
        "modules.configuration_task.service.resource_transfer_service.AgentFileTransferService.send_command",
        lambda *args, **kwargs: AgentFileCommandResult(
            True,
            {"size": 3, "sha256": "b" * 64} if args[1] == "file_publish_commit" else {},
        ),
    )
    try:
        ResourceTransferService.begin(
            db_session, RESOURCE_ID, ResourceTransferBeginModel(transferId="transfer-bad"), _current_user()
        )
        result = ResourceTransferService.commit(
            db_session, RESOURCE_ID, "transfer-bad", ResourceTransferCommitModel(), _current_user()
        )
        assert result.is_success is False
        assert result.result.error_code == "RESOURCE_METADATA_MISMATCH"
        assert db_session.get(ResourceObject, RESOURCE_ID).status == "FAILED"
        assert db_session.get(ResourceTransfer, "transfer-bad").status == "FAILED"
    finally:
        agents.pop("agent-01", None)
        agent_sessions.pop("agent-01", None)


def test_expired_transfer_cannot_accept_chunk(db_session):
    """超过传输 TTL 的活动记录进入 EXPIRED，不再接受分片。"""
    resource = _resource(status="UPLOADING")
    db_session.add(resource)
    db_session.add(
        ResourceTransfer(
            transfer_id="transfer-expired",
            resource_id=RESOURCE_ID,
            agent_code="agent-01",
            session_id="session-1",
            status="UPLOADING",
            expected_size=3,
            expected_sha256=SHA256,
            version=1,
            expires_at=datetime.now() - timedelta(minutes=1),
            create_by="tester",
            update_by="tester",
            create_time=datetime.now(),
            update_time=datetime.now(),
        )
    )
    db_session.commit()
    chunk = ResourceTransferChunkModel(
        index=0,
        offset=0,
        totalBytes=3,
        chunkBytes=3,
        chunkSha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        data="YWJj",
    )
    result = ResourceTransferService.chunk(db_session, RESOURCE_ID, "transfer-expired", chunk, _current_user())
    assert result.is_success is False
    assert result.result.status == "EXPIRED"
    assert db_session.get(ResourceObject, RESOURCE_ID).status == "FAILED"
