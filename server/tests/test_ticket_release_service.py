from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config.database import Base
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent
from modules.ticket.entity.vo.ticket_vo import (
    TicketReleaseBatchUpdateModel,
    TicketVersionStatisticsQueryModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.service.core.ticket_release_service import TicketReleaseService


@pytest.fixture()
def db_session():
    """创建内存数据库会话，用于验证版本治理服务的数据库写入。"""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def register_utf8_general_ci(dbapi_connection, connection_record):
        """SQLite 测试环境注册 MySQL 排序规则别名。"""
        _ = connection_record
        dbapi_connection.create_collation(
            "utf8_general_ci",
            lambda left, right: (left > right) - (left < right),
        )

    Base.metadata.create_all(engine, tables=[Ticket.__table__, TicketEvent.__table__])
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=[TicketEvent.__table__, Ticket.__table__])


def _current_user():
    """构造最小当前用户对象。"""
    return SimpleNamespace(user=SimpleNamespace(user_id=10, user_name="tester", nick_name="测试员"))


def _ticket(ticket_id: int, ticket_no: str, **overrides):
    """构造测试工单。"""
    data = {
        "ticket_id": ticket_id,
        "ticket_no": ticket_no,
        "title": f"工单 {ticket_no}",
        "status": TicketStatus.WAIT_VERIFY.value,
        "is_problem": True,
        "project_id": 1,
        "module_id": 2,
        "module_name": "支付模块",
        "issue_type_id": "bug",
        "issue_type_name": "缺陷",
        "root_cause_type": "配置错误",
        "solution_type": "代码修复",
        "resolution_code": "fixed",
        "resolution_name": "已修复",
        "problem_pattern_code": "timeout",
        "problem_pattern_name": "接口超时",
        "affected_version": "1.0.0",
        "planned_fix_version": "",
        "fixed_version": "",
        "released_version": "",
        "create_time": datetime(2026, 7, 10, 10, 0, 0),
        "update_time": datetime(2026, 7, 10, 10, 0, 0),
        "processed_at": datetime(2026, 7, 10, 11, 0, 0),
        "issue_id": ticket_id + 100,
        "del_flag": "0",
    }
    data.update(overrides)
    return Ticket(**data)


def test_batch_update_release_fields_writes_versions_and_events(db_session):
    """批量维护应写版本字段、发版/验证时间和对应事件。"""
    db_session.add(_ticket(1, "T-1"))
    db_session.add(_ticket(2, "T-2"))
    db_session.commit()
    released_at = datetime(2026, 7, 11, 9, 30, 0)
    payload = TicketReleaseBatchUpdateModel(
        ticketIds=[1, 2, 999],
        plannedFixVersion="1.0.1",
        fixedVersion="1.0.1",
        releasedVersion="1.0.1",
        releasedAt=released_at,
        markVerified=True,
        comment="周末发版",
    )

    result = TicketReleaseService.batch_update_release_fields(db_session, payload, _current_user())

    assert result.is_success is True
    assert result.result["updatedCount"] == 2
    assert result.result["missingTicketIds"] == [999]
    ticket = db_session.query(Ticket).filter(Ticket.ticket_id == 1).first()
    assert ticket.planned_fix_version == "1.0.1"
    assert ticket.fixed_version == "1.0.1"
    assert ticket.released_version == "1.0.1"
    assert ticket.released_at == released_at
    assert ticket.verified_at is not None
    events = db_session.query(TicketEvent).filter(TicketEvent.ticket_id == 1).all()
    assert {item.event_type for item in events} == {
        TicketEventType.DEPLOYED.value,
        TicketEventType.VERIFIED.value,
    }


def test_version_statistics_groups_affected_and_fix_versions(db_session):
    """版本统计应分别输出发生版本和修复/发版版本聚合行。"""
    db_session.add(
        _ticket(
            1,
            "T-1",
            affected_version="1.0.0",
            planned_fix_version="1.0.1",
            fixed_version="1.0.1",
            released_version="1.0.1",
            released_at=datetime(2026, 7, 11, 9, 0, 0),
            verified_at=datetime(2026, 7, 11, 10, 0, 0),
        )
    )
    db_session.add(
        _ticket(
            2,
            "T-2",
            affected_version="1.0.0",
            planned_fix_version="1.0.2",
            fixed_version="1.0.2",
            released_version="",
            processed_at=None,
            issue_id=101,
            status=TicketStatus.PROCESSING.value,
        )
    )
    db_session.commit()
    query = TicketVersionStatisticsQueryModel(projectIds="1", topLimit=3, versionLimit=20)

    result = TicketReleaseService.get_version_statistics(db_session, query)

    affected = result["affectedVersionRows"][0]
    assert affected["version"] == "1.0.0"
    assert affected["ticketCount"] == 2
    assert affected["problemCount"] == 2
    assert affected["issueCount"] == 1
    assert affected["unprocessedCount"] == 1
    fix_rows = {row["version"]: row for row in result["fixVersionRows"]}
    assert fix_rows["1.0.1"]["releasedCount"] == 1
    assert fix_rows["1.0.1"]["verifiedCount"] == 1
    assert fix_rows["1.0.2"]["ticketCount"] == 1
    assert fix_rows["未填写"]["ticketCount"] == 1
