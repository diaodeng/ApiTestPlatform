from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.database import Base
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_issue_vo import (
    TicketIssueBindModel,
    TicketIssueCreateAndBindModel,
    TicketIssueSimilarBindModel,
    TicketRelationCreateModel,
)
from modules.ticket.service.issue.ticket_issue_service import TicketIssueService
from modules.ticket.service.issue.ticket_relation_service import TicketRelationService


@pytest.fixture()
def db_session():
    """创建隔离的内存数据库会话。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_ticket(db_session, ticket_no: str, title: str, *, del_flag: str = "0") -> Ticket:
    """写入测试工单。"""
    ticket = Ticket(
        ticket_no=ticket_no,
        title=title,
        description=f"{title} 描述",
        project_id=1,
        merchant_name="项目A",
        module_id=2,
        module_name="模块B",
        root_cause_type="config",
        problem_pattern_code="pattern_a",
        problem_pattern_name="模式A",
        internal_owner_id=10,
        internal_owner_name="负责人",
        del_flag=del_flag,
    )
    db_session.add(ticket)
    db_session.commit()
    return ticket


def current_user():
    """构造服务层需要的当前用户对象。"""
    return SimpleNamespace(user=SimpleNamespace(user_id=1, user_name="tester", nick_name="测试员"))


def test_create_issue_and_bind_ticket(db_session):
    """创建 Issue 后绑定当前工单，应写入主归因字段并刷新影响数量。"""
    ticket = add_ticket(db_session, "T-1", "支付失败")

    result = TicketIssueService.create_issue_and_bind(
        db_session,
        ticket.ticket_id,
        TicketIssueCreateAndBindModel(title="支付失败真实问题"),
        current_user(),
    )

    db_session.refresh(ticket)
    assert result.is_success is True
    assert ticket.issue_id is not None
    assert ticket.issue_relation_type == "manual"
    assert ticket.issue_confirmed is True
    assert result.result["issue"]["affectedTicketCount"] == 1


def test_bind_from_similar_reuses_existing_issue(db_session):
    """相似工单已有 Issue 时，当前工单应复用该 Issue。"""
    source = add_ticket(db_session, "T-2", "会员支付超时")
    similar = add_ticket(db_session, "T-3", "同类支付超时")
    create_result = TicketIssueService.create_issue_and_bind(
        db_session,
        similar.ticket_id,
        TicketIssueCreateAndBindModel(title="支付超时问题"),
        current_user(),
    )
    issue_id = create_result.result["issue"]["issueId"]

    bind_result = TicketIssueService.bind_from_similar(
        db_session,
        source.ticket_id,
        TicketIssueSimilarBindModel(similarTicketId=similar.ticket_id, confidence=0.88),
        current_user(),
    )

    db_session.refresh(source)
    assert bind_result.is_success is True
    assert source.issue_id == issue_id
    assert bind_result.result["issue"]["affectedTicketCount"] == 2


def test_bind_from_similar_creates_issue_for_both_tickets(db_session):
    """相似工单没有 Issue 时，应先创建 Issue 并绑定两张工单。"""
    source = add_ticket(db_session, "T-4", "券核销失败")
    similar = add_ticket(db_session, "T-5", "券核销报错")

    result = TicketIssueService.bind_from_similar(
        db_session,
        source.ticket_id,
        TicketIssueSimilarBindModel(similarTicketId=similar.ticket_id, confidence=0.9),
        current_user(),
    )

    db_session.refresh(source)
    db_session.refresh(similar)
    assert result.is_success is True
    assert source.issue_id == similar.issue_id
    assert similar.issue_relation_type == "primary"
    assert result.result["issue"]["affectedTicketCount"] == 2


def test_unbind_refreshes_count_and_does_not_delete_issue(db_session):
    """解绑工单只刷新数量，不删除 Issue。"""
    ticket = add_ticket(db_session, "T-6", "库存同步异常")
    bind_result = TicketIssueService.create_issue_and_bind(
        db_session,
        ticket.ticket_id,
        TicketIssueCreateAndBindModel(title="库存同步问题"),
        current_user(),
    )
    issue_id = bind_result.result["issue"]["issueId"]

    unbind_result = TicketIssueService.unbind_ticket_issue(db_session, ticket.ticket_id, current_user())
    issue_detail = TicketIssueService.get_issue_detail_services(db_session, issue_id)
    db_session.refresh(ticket)

    assert unbind_result.is_success is True
    assert ticket.issue_id is None
    assert issue_detail["issueId"] == issue_id
    assert issue_detail["affectedTicketCount"] == 0


def test_repeated_bind_same_issue_is_idempotent(db_session):
    """同一工单重复绑定同一 Issue 应幂等成功，不重复计数。"""
    ticket = add_ticket(db_session, "T-7", "打印失败")
    bind_result = TicketIssueService.create_issue_and_bind(
        db_session,
        ticket.ticket_id,
        TicketIssueCreateAndBindModel(title="打印问题"),
        current_user(),
    )
    issue_id = bind_result.result["issue"]["issueId"]

    second_result = TicketIssueService.bind_ticket_to_issue(
        db_session,
        ticket.ticket_id,
        TicketIssueBindModel(issueId=issue_id),
        current_user(),
    )

    assert second_result.is_success is True
    assert second_result.result["issue"]["affectedTicketCount"] == 1


def test_relation_does_not_change_primary_issue(db_session):
    """补充关系创建、确认、删除不影响工单主归因。"""
    source = add_ticket(db_session, "T-8", "登录异常")
    target = add_ticket(db_session, "T-9", "登录失败")
    relation_result = TicketRelationService.create_relation(
        db_session,
        TicketRelationCreateModel(sourceTicketId=source.ticket_id, targetTicketId=target.ticket_id),
        current_user(),
    )

    TicketRelationService.confirm_relation(db_session, relation_result.result["relationId"], current_user())
    TicketRelationService.delete_relation(db_session, relation_result.result["relationId"], current_user())
    db_session.refresh(source)
    db_session.refresh(target)

    assert source.issue_id is None
    assert target.issue_id is None


def test_soft_deleted_ticket_not_counted(db_session):
    """软删除工单不计入 Issue 影响数量。"""
    active = add_ticket(db_session, "T-10", "活动工单")
    deleted = add_ticket(db_session, "T-11", "删除工单")
    bind_result = TicketIssueService.create_issue_and_bind(
        db_session,
        active.ticket_id,
        TicketIssueCreateAndBindModel(title="计数问题"),
        current_user(),
    )
    issue_id = bind_result.result["issue"]["issueId"]
    TicketIssueService.bind_ticket_to_issue(
        db_session,
        deleted.ticket_id,
        TicketIssueBindModel(issueId=issue_id),
        current_user(),
    )
    deleted.del_flag = "2"
    db_session.commit()

    count = TicketIssueService.refresh_affected_ticket_count(db_session, issue_id, current_user())

    assert count == 1
