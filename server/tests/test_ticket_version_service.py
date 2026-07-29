from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config.database import Base
from modules.ticket.entity.do.ticket_do import Ticket, TicketVersion, TicketVersionRelease
from modules.ticket.entity.vo.ticket_version_vo import (
    TicketVersionListItemResponseModel,
    TicketVersionOptionResponseModel,
    TicketVersionOptionsQueryModel,
    TicketVersionQueryModel,
    TicketVersionReleaseCreateModel,
)
from modules.ticket.enums.ticket_enums import TicketStatus
from modules.ticket.service.core.ticket_version_service import TicketVersionService


@pytest.fixture()
def db_session():
    """创建版本中心服务使用的内存数据库会话。"""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def register_utf8_general_ci(dbapi_connection, connection_record):
        """SQLite 测试环境注册 MySQL 排序规则别名。"""
        _ = connection_record
        dbapi_connection.create_collation(
            "utf8_general_ci",
            lambda left, right: (left > right) - (left < right),
        )

    tables = [Ticket.__table__, TicketVersion.__table__, TicketVersionRelease.__table__]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))


def _current_user():
    """构造最小当前用户对象。"""
    return SimpleNamespace(user=SimpleNamespace(user_name="tester"))


def _ticket() -> Ticket:
    """构造待关联版本中心的工单。"""
    return Ticket(
        ticket_id=1001,
        ticket_no="TV-1001",
        title="版本中心测试工单",
        project_id=10,
        merchant_name="测试项目",
        status=TicketStatus.PROCESSING.value,
        create_time=datetime(2026, 7, 29, 10, 0, 0),
        update_time=datetime(2026, 7, 29, 10, 0, 0),
    )


def test_assign_detected_ticket_version_creates_discovered_candidate(db_session, monkeypatch):
    """工单自动发现版本时应创建待确认版本且只回写关联ID。"""
    ticket = _ticket()
    db_session.add(ticket)
    db_session.flush()
    monkeypatch.setattr(TicketVersionService, "resolve_project_name", lambda *args, **kwargs: "测试项目")

    TicketVersionService.assign_detected_ticket_version(
        db_session,
        ticket,
        version_type="affected",
        version_key="release/2.1.3",
        source="log_extract",
    )
    db_session.commit()

    version = db_session.query(TicketVersion).one()
    assert version.version_key == "release/2.1.3"
    assert version.lifecycle_status == "discovered"
    assert version.source == "log_extract"
    assert ticket.affected_version_id == version.version_id


def test_save_release_does_not_close_ticket(db_session):
    """登记已发布事实不能直接改变关联工单状态。"""
    ticket = _ticket()
    version = TicketVersion(
        version_id=2001,
        project_id=10,
        project_name="测试项目",
        version_key="release/2.1.3",
        version_name="release/2.1.3",
        lifecycle_status="confirmed",
        source="manual",
        enabled=True,
    )
    ticket.affected_version_id = version.version_id
    db_session.add_all([ticket, version])
    db_session.commit()
    payload = TicketVersionReleaseCreateModel(
        versionId=version.version_id,
        environment="production",
        releaseStatus="released",
    )

    result = TicketVersionService.save_release(db_session, payload, _current_user())

    assert result.is_success is True
    assert db_session.query(TicketVersionRelease).one().released_at is not None
    updated_ticket = db_session.query(Ticket).filter(Ticket.ticket_id == ticket.ticket_id).one()
    assert updated_ticket.status == TicketStatus.PROCESSING.value


def test_list_version_services_uses_orm_entity_before_response_serialization(db_session):
    """版本分页应使用 ORM 实体完成业务编排，再输出 Pydantic 响应模型。"""
    version = TicketVersion(
        version_id=3001,
        project_id=10,
        project_name="测试项目",
        version_key="release/3.0.0",
        version_name="release/3.0.0",
        lifecycle_status="confirmed",
        source="manual",
        enabled=True,
    )
    release = TicketVersionRelease(
        release_id=3002,
        version_id=version.version_id,
        environment="production",
        batch_no="default",
        release_status="released",
        release_by="tester",
    )
    db_session.add_all([version, release])
    db_session.commit()

    result = TicketVersionService.list_version_services(
        db_session,
        TicketVersionQueryModel(projectId=10, pageNum=1, pageSize=10, isPage=True),
    )

    assert isinstance(result.rows[0], TicketVersionListItemResponseModel)
    assert result.rows[0].version_id == str(version.version_id)
    assert result.rows[0].release_count == 1
    assert result.rows[0].latest_release.release_by == "tester"


def test_version_options_query_model_accepts_camel_case_api_parameter():
    """版本选项接口应通过 Pydantic 查询模型接收前端 projectId。"""
    query = TicketVersionOptionsQueryModel(projectId=10, includeDiscovered=False)

    assert query.project_id == 10
    assert query.include_discovered is False


def test_version_option_response_model_accepts_service_snake_case_fields():
    """版本选项响应模型应接受服务层 snake_case 字段并输出 camelCase。"""
    option = TicketVersionOptionResponseModel(
        version_id=10,
        version_key="release/1.0.0",
        version_name="release/1.0.0",
        lifecycle_status="confirmed",
        default_branch="release/1.0.0",
    )

    assert option.model_dump(by_alias=True)["versionId"] == "10"


def test_version_response_serializes_large_id_as_exact_string():
    """超过 JavaScript 安全整数范围的版本 ID 必须以字符串响应。"""
    option = TicketVersionOptionResponseModel(
        version_id=101949241739444232,
        version_key="release/1.0.0",
        version_name="release/1.0.0",
        lifecycle_status="confirmed",
    )

    assert option.version_id == "101949241739444232"
