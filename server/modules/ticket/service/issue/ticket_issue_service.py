from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_issue_dao import TicketIssueDao
from modules.ticket.entity.do.ticket_do import Ticket, TicketIssue, TicketRelation
from modules.ticket.entity.vo.ticket_issue_vo import (
    TicketIssueBindModel,
    TicketIssueCreateAndBindModel,
    TicketIssueCreateModel,
    TicketIssueQueryModel,
    TicketIssueSimilarBindModel,
    TicketIssueUpdateModel,
    dump_model,
)
from modules.ticket.util.ticket_common_util import user_name
from utils.common_util import CamelCaseUtil
from utils.snowflake import snowIdWorker


class TicketIssueService:
    """
    问题实例归因服务，负责 Issue 创建、工单绑定、解绑、相似工单确认和影响工单数刷新。
    """

    @classmethod
    def get_issue_list_services(cls, query_db: Session, query: TicketIssueQueryModel):
        """
        查询问题实例列表。
        :param query_db: 数据库会话
        :param query: 查询条件
        :return: 分页结果或列表
        """
        return TicketIssueDao.get_issue_list(query_db, query)

    @classmethod
    def get_issue_detail_services(cls, query_db: Session, issue_id: int) -> dict[str, Any] | None:
        """
        查询问题实例详情，并附带已绑定工单列表。
        :param query_db: 数据库会话
        :param issue_id: 问题实例ID
        :return: Issue 详情
        """
        issue = TicketIssueDao.get_issue_by_id(query_db, issue_id)
        if not issue:
            return None
        result = CamelCaseUtil.transform_result(issue)
        result["tickets"] = CamelCaseUtil.transform_result(TicketIssueDao.list_tickets_by_issue_id(query_db, issue_id))
        return result

    @classmethod
    def create_issue(
        cls,
        query_db: Session,
        issue_object: TicketIssueCreateModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        手工创建问题实例。
        :param query_db: 数据库会话
        :param issue_object: 创建参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        try:
            issue = cls.create_issue_entity(query_db, issue_object, current_user)
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="问题实例创建成功",
                result=CamelCaseUtil.transform_result(issue),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def update_issue(
        cls,
        query_db: Session,
        issue_object: TicketIssueUpdateModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        编辑问题实例基础信息。
        :param query_db: 数据库会话
        :param issue_object: 编辑参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        issue = TicketIssueDao.get_issue_by_id(query_db, issue_object.issue_id)
        if not issue:
            return CrudResponseModel(is_success=False, message="问题实例不存在")
        try:
            data = dump_model(issue_object)
            data.pop("issue_id", None)
            data.pop("issue_no", None)
            data["update_by"] = user_name(current_user)
            data["update_time"] = datetime.now()
            TicketIssueDao.update_issue(query_db, issue.issue_id, data)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="问题实例更新成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def bind_ticket_to_issue(
        cls,
        query_db: Session,
        ticket_id: int,
        bind_object: TicketIssueBindModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        将工单绑定到已有问题实例，同一工单重复绑定同一 Issue 幂等成功。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param bind_object: 绑定参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        ticket = TicketIssueDao.get_ticket_by_id(query_db, ticket_id)
        issue = TicketIssueDao.get_issue_by_id(query_db, bind_object.issue_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        if not issue:
            return CrudResponseModel(is_success=False, message="问题实例不存在")
        try:
            previous_issue_id = ticket.issue_id
            cls.apply_ticket_issue_binding(
                query_db,
                ticket=ticket,
                issue=issue,
                relation_type=bind_object.relation_type or "manual",
                confirmed=bind_object.confirmed,
                current_user=current_user,
            )
            cls.refresh_affected_ticket_count(query_db, issue.issue_id, current_user)
            if previous_issue_id and previous_issue_id != issue.issue_id:
                cls.refresh_affected_ticket_count(query_db, previous_issue_id, current_user)
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="工单归因绑定成功",
                result=cls.build_ticket_issue_result(query_db, ticket_id),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def create_issue_and_bind(
        cls,
        query_db: Session,
        ticket_id: int,
        issue_object: TicketIssueCreateAndBindModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        创建问题实例并绑定当前工单。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param issue_object: 创建并绑定参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        ticket = TicketIssueDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        try:
            issue = cls.create_issue_entity(
                query_db,
                issue_object,
                current_user,
                source_ticket=ticket,
                first_ticket_id=ticket.ticket_id,
            )
            cls.apply_ticket_issue_binding(
                query_db,
                ticket=ticket,
                issue=issue,
                relation_type=issue_object.relation_type or "manual",
                confirmed=issue_object.confirmed,
                current_user=current_user,
            )
            cls.refresh_affected_ticket_count(query_db, issue.issue_id, current_user)
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="问题实例创建并绑定成功",
                result=cls.build_ticket_issue_result(query_db, ticket_id),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def bind_from_similar(
        cls,
        query_db: Session,
        ticket_id: int,
        bind_object: TicketIssueSimilarBindModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        从相似工单人工确认归因：相似工单已有 Issue 则复用，否则先以相似工单创建 Issue 并绑定两张工单。
        :param query_db: 数据库会话
        :param ticket_id: 当前工单ID
        :param bind_object: 相似工单绑定参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        ticket = TicketIssueDao.get_ticket_by_id(query_db, ticket_id)
        similar_ticket = TicketIssueDao.get_ticket_by_id(query_db, bind_object.similar_ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="当前工单不存在")
        if not similar_ticket:
            return CrudResponseModel(is_success=False, message="相似工单不存在")
        if ticket.ticket_id == similar_ticket.ticket_id:
            return CrudResponseModel(is_success=False, message="不能将工单归入自身")

        try:
            changed_issue_ids = {ticket.issue_id, similar_ticket.issue_id}
            issue = TicketIssueDao.get_issue_by_id(query_db, similar_ticket.issue_id)
            if not issue:
                issue = cls.create_issue_from_ticket(query_db, similar_ticket, current_user)
                cls.apply_ticket_issue_binding(
                    query_db,
                    ticket=similar_ticket,
                    issue=issue,
                    relation_type="primary",
                    confirmed=True,
                    current_user=current_user,
                )
            cls.apply_ticket_issue_binding(
                query_db,
                ticket=ticket,
                issue=issue,
                relation_type=bind_object.relation_type or "similar",
                confirmed=True,
                current_user=current_user,
            )
            cls.upsert_similarity_relation(query_db, ticket, similar_ticket, bind_object, current_user)
            changed_issue_ids.add(issue.issue_id)
            for issue_id in changed_issue_ids:
                if issue_id:
                    cls.refresh_affected_ticket_count(query_db, issue_id, current_user)
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="相似工单归因确认成功",
                result=cls.build_ticket_issue_result(query_db, ticket_id),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def unbind_ticket_issue(
        cls,
        query_db: Session,
        ticket_id: int,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        解除工单主归因，不删除问题实例。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :param current_user: 当前用户
        :return: 操作结果
        """
        ticket = TicketIssueDao.get_ticket_by_id(query_db, ticket_id)
        if not ticket:
            return CrudResponseModel(is_success=False, message="工单不存在")
        previous_issue_id = ticket.issue_id
        if not previous_issue_id:
            return CrudResponseModel(is_success=True, message="工单未绑定问题实例")
        try:
            TicketIssueDao.update_ticket_issue(query_db, ticket.ticket_id, None, "", False, user_name(current_user))
            cls.refresh_affected_ticket_count(query_db, previous_issue_id, current_user)
            query_db.commit()
            return CrudResponseModel(is_success=True, message="工单归因解除成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def create_issue_entity(
        cls,
        query_db: Session,
        issue_object: TicketIssueCreateModel,
        current_user: CurrentUserModel | None,
        *,
        source_ticket: Ticket | None = None,
        first_ticket_id: int | None = None,
    ) -> TicketIssue:
        """
        创建 Issue 实体但不提交事务，供组合服务复用。
        :param query_db: 数据库会话
        :param issue_object: 创建参数
        :param current_user: 当前用户
        :param source_ticket: 可选来源工单，用于补齐归属字段
        :param first_ticket_id: 首张工单ID
        :return: 保存后的 Issue
        """
        data = dump_model(issue_object)
        data.pop("issue_id", None)
        data.pop("affected_ticket_count", None)
        data.pop("relation_type", None)
        data.pop("confirmed", None)
        data["issue_no"] = data.get("issue_no") or cls.generate_issue_no()
        source_title = source_ticket.title if source_ticket else ""
        data["title"] = str(data.get("title") or source_title or "").strip()
        data["first_ticket_id"] = (
            data.get("first_ticket_id") or first_ticket_id or getattr(source_ticket, "ticket_id", None)
        )
        cls.fill_issue_data_from_ticket(data, source_ticket)
        data["create_by"] = user_name(current_user)
        data["update_by"] = user_name(current_user)
        return TicketIssueDao.add_issue(query_db, TicketIssue(**data))

    @classmethod
    def create_issue_from_ticket(
        cls,
        query_db: Session,
        ticket: Ticket,
        current_user: CurrentUserModel | None,
    ) -> TicketIssue:
        """
        根据工单创建 Issue，用于相似工单还没有问题实例时的自动补齐。
        :param query_db: 数据库会话
        :param ticket: 来源工单
        :param current_user: 当前用户
        :return: 保存后的 Issue
        """
        issue_object = TicketIssueCreateModel(
            title=ticket.title or ticket.ticket_no,
            summary=ticket.root_cause or ticket.description,
            status="open",
        )
        return cls.create_issue_entity(query_db, issue_object, current_user, source_ticket=ticket)

    @classmethod
    def apply_ticket_issue_binding(
        cls,
        query_db: Session,
        *,
        ticket: Ticket,
        issue: TicketIssue,
        relation_type: str,
        confirmed: bool,
        current_user: CurrentUserModel | None,
    ) -> None:
        """
        写入工单主归因字段；同一工单重复绑定同一 Issue 保持幂等。
        :param query_db: 数据库会话
        :param ticket: 工单实体
        :param issue: Issue 实体
        :param relation_type: 归属类型
        :param confirmed: 是否确认
        :param current_user: 当前用户
        :return: 无
        """
        if (
            ticket.issue_id == issue.issue_id
            and ticket.issue_relation_type == relation_type
            and bool(ticket.issue_confirmed) == bool(confirmed)
        ):
            return
        TicketIssueDao.update_ticket_issue(
            query_db,
            ticket.ticket_id,
            issue.issue_id,
            relation_type,
            confirmed,
            user_name(current_user),
        )
        ticket.issue_id = issue.issue_id
        ticket.issue_relation_type = relation_type
        ticket.issue_confirmed = confirmed

    @classmethod
    def refresh_affected_ticket_count(
        cls,
        query_db: Session,
        issue_id: int,
        current_user: CurrentUserModel | None,
    ) -> int:
        """
        刷新 Issue 影响工单数，软删除工单不计入。
        :param query_db: 数据库会话
        :param issue_id: Issue ID
        :param current_user: 当前用户
        :return: 最新数量
        """
        count = TicketIssueDao.count_tickets_by_issue_id(query_db, issue_id)
        TicketIssueDao.update_issue(
            query_db,
            issue_id,
            {
                "affected_ticket_count": count,
                "update_by": user_name(current_user),
                "update_time": datetime.now(),
            },
        )
        return count

    @classmethod
    def build_ticket_issue_result(cls, query_db: Session, ticket_id: int) -> dict[str, Any]:
        """
        构造绑定操作返回结果。
        :param query_db: 数据库会话
        :param ticket_id: 工单ID
        :return: 当前工单与 Issue 摘要
        """
        ticket = TicketIssueDao.get_ticket_by_id(query_db, ticket_id)
        issue = TicketIssueDao.get_issue_by_id(query_db, ticket.issue_id if ticket else None)
        return {
            "ticket": CamelCaseUtil.transform_result(ticket) if ticket else None,
            "issue": CamelCaseUtil.transform_result(issue) if issue else None,
        }

    @classmethod
    def fill_issue_data_from_ticket(cls, data: dict[str, Any], ticket: Ticket | None) -> None:
        """
        从来源工单补齐 Issue 归属字段，入参已填值不覆盖。
        :param data: Issue 字段字典
        :param ticket: 来源工单
        :return: 无
        """
        if not ticket:
            return
        data["summary"] = data.get("summary") or ticket.root_cause or ticket.description
        data["severity"] = data.get("severity") or ticket.severity or ticket.internal_priority or ""
        data["project_id"] = data.get("project_id") or ticket.project_id
        data["project_name"] = data.get("project_name") or ticket.merchant_name or ""
        data["module_id"] = data.get("module_id") or ticket.module_id
        data["module_name"] = data.get("module_name") or ticket.module_name or ""
        data["root_cause_type"] = data.get("root_cause_type") or ticket.root_cause_type or ""
        data["problem_pattern_code"] = data.get("problem_pattern_code") or ticket.problem_pattern_code or ""
        data["problem_pattern_name"] = data.get("problem_pattern_name") or ticket.problem_pattern_name or ""
        data["owner_id"] = data.get("owner_id") or ticket.internal_owner_id or ticket.current_assignee_id
        data["owner_name"] = data.get("owner_name") or ticket.internal_owner_name or ticket.current_assignee_name or ""

    @classmethod
    def upsert_similarity_relation(
        cls,
        query_db: Session,
        ticket: Ticket,
        similar_ticket: Ticket,
        bind_object: TicketIssueSimilarBindModel,
        current_user: CurrentUserModel | None,
    ) -> None:
        """
        幂等保存相似工单补充关系，供后续复盘相似来源。
        :param query_db: 数据库会话
        :param ticket: 当前工单
        :param similar_ticket: 相似工单
        :param bind_object: 绑定参数
        :param current_user: 当前用户
        :return: 无
        """
        relation_type = bind_object.relation_type or "similar"
        existing = TicketIssueDao.get_relation(query_db, ticket.ticket_id, similar_ticket.ticket_id, relation_type)
        data = {
            "confidence": bind_object.confidence,
            "source": "manual",
            "confirmed": True,
            "remark": bind_object.remark,
            "update_by": user_name(current_user),
            "update_time": datetime.now(),
        }
        if existing:
            TicketIssueDao.update_relation(query_db, existing.relation_id, data)
            return
        data.update(
            {
                "source_ticket_id": ticket.ticket_id,
                "target_ticket_id": similar_ticket.ticket_id,
                "relation_type": relation_type,
                "create_by": user_name(current_user),
            }
        )
        TicketIssueDao.add_relation(query_db, TicketRelation(**data))

    @staticmethod
    def generate_issue_no() -> str:
        """
        生成问题实例编号。
        :return: 问题实例编号
        """
        return f"ISS{datetime.now().strftime('%Y%m%d')}{snowIdWorker.get_id()}"
