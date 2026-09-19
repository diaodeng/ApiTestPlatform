"""资源领域最小切片测试。"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.database import Base
from modules.configuration_task.entity.do.resource_object_do import ResourceObject
from modules.configuration_task.entity.vo.resource_vo import ResourceCreateModel, ResourceReadyModel
from modules.configuration_task.service.resource_service import ResourceService

SHA256 = "a" * 64


@pytest.fixture
def db_session():
    """创建资源领域测试所需的独立 SQLite 会话。"""
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[ResourceObject.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def _current_user() -> SimpleNamespace:
    """构造资源服务所需的最小当前用户对象。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester"))


def test_resource_detail_serializes_snowflake_id_as_string():
    """资源详情响应必须将 BIGINT resource_id 序列化为字符串。"""
    row = ResourceObject(
        resource_id=9223372036854770000,
        provider_type="agent_local",
        provider_execution_side="agent",
        agent_code="agent-01",
        object_key="inputs/demo.xlsx",
        original_file_name="demo.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_size=12,
        checksum_algorithm="sha256",
        sha256=SHA256,
        version=1,
        status="READY",
        create_by="tester",
        update_by="tester",
        create_time=datetime.now(),
        update_time=datetime.now(),
    )

    response = ResourceService.to_detail_model(row)

    assert response is not None
    assert response.resource_id == "9223372036854770000"
    assert response.model_dump(by_alias=True)["resourceId"] == "9223372036854770000"


def test_resource_create_rejects_absolute_or_parent_object_key():
    """资源 objectKey 不得携带绝对路径或路径穿越。"""
    with pytest.raises(ValidationError):
        ResourceCreateModel(
            agentCode="agent-01",
            objectKey="C:/Users/test/demo.xlsx",
            originalFileName="demo.xlsx",
            fileSize=1,
            sha256=SHA256,
        )

    with pytest.raises(ValidationError):
        ResourceCreateModel(
            agentCode="agent-01",
            objectKey="inputs/../demo.xlsx",
            originalFileName="demo.xlsx",
            fileSize=1,
            sha256=SHA256,
        )


def test_resource_create_normalizes_sha256_and_starts_pending():
    """创建契约应归一化摘要，服务写入的资源初始状态为 PENDING。"""
    model = ResourceCreateModel(
        agentCode=" agent-01 ",
        objectKey="inputs/demo.xlsx",
        originalFileName="demo.xlsx",
        fileSize=12,
        sha256=SHA256.upper(),
    )
    assert model.sha256 == SHA256
    assert model.agent_code == "agent-01"


def test_resource_ready_rejects_metadata_mismatch(db_session, monkeypatch):
    """ready 确认的大小或摘要不匹配时资源必须进入 FAILED。"""
    row = ResourceObject(
        resource_id=1234567890123456,
        provider_type="agent_local",
        provider_execution_side="agent",
        agent_code="agent-01",
        object_key="inputs/demo.xlsx",
        original_file_name="demo.xlsx",
        mime_type="application/octet-stream",
        file_size=12,
        checksum_algorithm="sha256",
        sha256=SHA256,
        version=1,
        status="PENDING",
        create_by="tester",
        update_by="tester",
        create_time=datetime.now(),
        update_time=datetime.now(),
    )
    db_session.add(row)
    db_session.commit()

    result = ResourceService.mark_ready(
        db_session,
        row.resource_id,
        ResourceReadyModel(fileSize=13, sha256=SHA256),
        _current_user(),
    )

    assert result.is_success is False
    assert db_session.get(ResourceObject, row.resource_id).status == "FAILED"
