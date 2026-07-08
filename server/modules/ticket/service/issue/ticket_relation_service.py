from datetime import datetime

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_issue_dao import TicketIssueDao
from modules.ticket.entity.do.ticket_do import TicketRelation
from modules.ticket.entity.vo.ticket_issue_vo import TicketRelationCreateModel, dump_model
from modules.ticket.util.ticket_common_util import user_name
from utils.common_util import CamelCaseUtil


class TicketRelationService:
    """
    工单补充关系服务，只维护相似、重复、关联等辅助关系，不修改工单主归因字段。
    """

    @classmethod
    def create_relation(
        cls,
        query_db: Session,
        relation_object: TicketRelationCreateModel,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        创建或更新工单补充关系，重复关系按同一方向同一类型幂等更新。
        :param query_db: 数据库会话
        :param relation_object: 关系参数
        :param current_user: 当前用户
        :return: 操作结果
        """
        source_ticket = TicketIssueDao.get_ticket_by_id(query_db, relation_object.source_ticket_id)
        target_ticket = TicketIssueDao.get_ticket_by_id(query_db, relation_object.target_ticket_id)
        if not source_ticket or not target_ticket:
            return CrudResponseModel(is_success=False, message="源工单或目标工单不存在")

        operator = user_name(current_user)
        existing = TicketIssueDao.get_relation(
            query_db,
            relation_object.source_ticket_id,
            relation_object.target_ticket_id,
            relation_object.relation_type or "similar",
        )
        try:
            data = dump_model(relation_object)
            now = datetime.now()
            if existing:
                data["update_by"] = operator
                data["update_time"] = now
                TicketIssueDao.update_relation(query_db, existing.relation_id, data)
                query_db.commit()
                query_db.refresh(existing)
                return CrudResponseModel(
                    is_success=True,
                    message="关系更新成功",
                    result=CamelCaseUtil.transform_result(existing),
                )
            data["create_by"] = operator
            data["update_by"] = operator
            relation = TicketIssueDao.add_relation(query_db, TicketRelation(**data))
            query_db.commit()
            return CrudResponseModel(
                is_success=True,
                message="关系创建成功",
                result=CamelCaseUtil.transform_result(relation),
            )
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def confirm_relation(
        cls,
        query_db: Session,
        relation_id: int,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        确认工单补充关系。
        :param query_db: 数据库会话
        :param relation_id: 关系ID
        :param current_user: 当前用户
        :return: 操作结果
        """
        relation = TicketIssueDao.get_relation_by_id(query_db, relation_id)
        if not relation:
            return CrudResponseModel(is_success=False, message="工单关系不存在")
        try:
            TicketIssueDao.update_relation(
                query_db,
                relation_id,
                {
                    "confirmed": True,
                    "update_by": user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="关系确认成功")
        except Exception:
            query_db.rollback()
            raise

    @classmethod
    def delete_relation(
        cls,
        query_db: Session,
        relation_id: int,
        current_user: CurrentUserModel | None,
    ) -> CrudResponseModel:
        """
        软删除工单补充关系。
        :param query_db: 数据库会话
        :param relation_id: 关系ID
        :param current_user: 当前用户
        :return: 操作结果
        """
        relation = TicketIssueDao.get_relation_by_id(query_db, relation_id)
        if not relation:
            return CrudResponseModel(is_success=False, message="工单关系不存在")
        try:
            TicketIssueDao.update_relation(
                query_db,
                relation_id,
                {
                    "del_flag": "2",
                    "update_by": user_name(current_user),
                    "update_time": datetime.now(),
                },
            )
            query_db.commit()
            return CrudResponseModel(is_success=True, message="关系删除成功")
        except Exception:
            query_db.rollback()
            raise
