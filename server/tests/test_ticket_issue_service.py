from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.database import Base
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_issue_vo import (
    TicketIssueBatchBindModel,
    TicketIssueBindByTicketNoModel,
    TicketIssueBindModel,
    TicketIssueCreateAndBindModel,
    TicketIssueCreateModel,
    TicketIssueSimilarBindModel,
    TicketIssueTicketOptionQueryModel,
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




def test_issue_create_normalizes_blank_optional_integer_fields():
    """问题实例新增表单的空整数值应归一化为空值。"""
    model = TicketIssueCreateModel(title="测试问题", ownerId="", projectId="", moduleId="")

    assert model.owner_id is None
    assert model.project_id is None
    assert model.module_id is None

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




def test_search_and_bind_ticket_by_no_returns_business_numbers(db_session):
    """问题详情应支持按工单号搜索并绑定，首张工单返回业务工单号。"""
    first = add_ticket(db_session, "T-12", "支付失败")
    second = add_ticket(db_session, "T-13", "支付超时")
    create_result = TicketIssueService.create_issue_and_bind(
        db_session,
        first.ticket_id,
        TicketIssueCreateAndBindModel(title="支付链路问题"),
        current_user(),
    )
    issue_id = create_result.result["issue"]["issueId"]

    options = TicketIssueService.search_tickets_for_issue(
        db_session,
        TicketIssueTicketOptionQueryModel(keyword="T-13"),
    )
    assert [row["ticketNo"] for row in options] == ["T-13"]

    bind_result = TicketIssueService.bind_ticket_by_no(
        db_session,
        issue_id,
        TicketIssueBindByTicketNoModel(ticketNo="T-13"),
        current_user(),
    )
    detail = TicketIssueService.get_issue_detail_services(db_session, issue_id)

    assert bind_result.is_success is True
    assert detail["firstTicketNo"] == "T-12"
    assert {row["ticketNo"] for row in detail["tickets"]} == {"T-12", "T-13"}
    db_session.refresh(second)
    assert second.issue_id == issue_id


def test_batch_bind_tickets_to_existing_issue(db_session):
    """批量关联多个未归因工单应一次成功并刷新影响工单数。"""
    target = add_ticket(db_session, "T-14", "目标问题")
    ticket_a = add_ticket(db_session, "T-15", "同类问题A")
    ticket_b = add_ticket(db_session, "T-16", "同类问题B")
    create_result = TicketIssueService.create_issue_and_bind(
        db_session,
        target.ticket_id,
        TicketIssueCreateAndBindModel(title="目标 Issue"),
        current_user(),
    )
    issue_id = create_result.result["issue"]["issueId"]

    result = TicketIssueService.batch_bind_tickets_to_issue(
        db_session,
        TicketIssueBatchBindModel(ticketNos=[ticket_a.ticket_no, ticket_b.ticket_no], issueId=issue_id),
        current_user(),
    )

    assert result.is_success is True
    assert result.result["successCount"] == 2
    assert result.result["issue"]["affectedTicketCount"] == 3
    db_session.refresh(ticket_a)
    db_session.refresh(ticket_b)
    assert ticket_a.issue_id == issue_id
    assert ticket_b.issue_id == issue_id


def test_batch_bind_rejects_existing_issue_conflict_without_partial_update(db_session):
    """批量关联遇到其他 Issue 时默认整体拒绝，不得留下部分绑定。"""
    source = add_ticket(db_session, "T-17", "已有问题")
    pending = add_ticket(db_session, "T-18", "待关联问题")
    target = add_ticket(db_session, "T-19", "目标问题")
    source_result = TicketIssueService.create_issue_and_bind(
        db_session,
        source.ticket_id,
        TicketIssueCreateAndBindModel(title="旧 Issue"),
        current_user(),
    )
    target_result = TicketIssueService.create_issue_and_bind(
        db_session,
        target.ticket_id,
        TicketIssueCreateAndBindModel(title="新 Issue"),
        current_user(),
    )
    old_issue_id = source_result.result["issue"]["issueId"]
    target_issue_id = target_result.result["issue"]["issueId"]

    result = TicketIssueService.batch_bind_tickets_to_issue(
        db_session,
        TicketIssueBatchBindModel(ticketNos=[source.ticket_no, pending.ticket_no], issueId=target_issue_id),
        current_user(),
    )

    assert result.is_success is False
    assert result.result["successCount"] == 0
    assert source.ticket_no in {row["ticketNo"] for row in result.result["conflicts"]}
    db_session.refresh(source)
    db_session.refresh(pending)
    assert source.issue_id == old_issue_id
    assert pending.issue_id is None


def test_batch_bind_allow_reassign_refreshes_old_issue(db_session):
    """显式允许重新归因时应转移工单并刷新旧、新 Issue 数量。"""
    source = add_ticket(db_session, "T-20", "待转移问题")
    target = add_ticket(db_session, "T-21", "目标问题")
    old_result = TicketIssueService.create_issue_and_bind(
        db_session,
        source.ticket_id,
        TicketIssueCreateAndBindModel(title="旧问题"),
        current_user(),
    )
    target_result = TicketIssueService.create_issue_and_bind(
        db_session,
        target.ticket_id,
        TicketIssueCreateAndBindModel(title="目标问题"),
        current_user(),
    )
    old_issue_id = old_result.result["issue"]["issueId"]
    target_issue_id = target_result.result["issue"]["issueId"]

    result = TicketIssueService.batch_bind_tickets_to_issue(
        db_session,
        TicketIssueBatchBindModel(
            ticketNos=[source.ticket_no],
            issueId=target_issue_id,
            allowReassign=True,
        ),
        current_user(),
    )

    assert result.is_success is True
    db_session.refresh(source)
    assert source.issue_id == target_issue_id
    old_detail = TicketIssueService.get_issue_detail_services(db_session, old_issue_id)
    new_detail = TicketIssueService.get_issue_detail_services(db_session, target_issue_id)
    assert old_detail["affectedTicketCount"] == 0
    assert new_detail["affectedTicketCount"] == 2


def test_batch_bind_rejects_cross_project_ticket(db_session):
    """批量关联默认拒绝工单和 Issue 项目不一致。"""
    ticket = add_ticket(db_session, "T-22", "跨项目问题")
    target = add_ticket(db_session, "T-23", "目标问题")
    target_result = TicketIssueService.create_issue_and_bind(
        db_session,
        target.ticket_id,
        TicketIssueCreateAndBindModel(title="项目A问题"),
        current_user(),
    )
    issue_id = target_result.result["issue"]["issueId"]
    ticket.project_id = 2
    db_session.commit()

    result = TicketIssueService.batch_bind_tickets_to_issue(
        db_session,
        TicketIssueBatchBindModel(ticketNos=[ticket.ticket_no], issueId=issue_id),
        current_user(),
    )

    assert result.is_success is False
    assert result.result["projectConflicts"][0]["ticketNo"] == "T-22"
    db_session.refresh(ticket)
    assert ticket.issue_id is None


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
