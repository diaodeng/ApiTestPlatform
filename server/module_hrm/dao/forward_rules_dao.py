from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.forward_rules_do import QtrForwardRules, QtrForwardRulesDetail
from module_hrm.entity.dto.forward_rules_dto import ForwardRulesModelForApi
from module_hrm.entity.vo.forward_rules_vo import ForwardRulesModel, ForwardRulesQueryModel, ForwardRulesDeleteModel, \
    ForwardRulesDetailQueryModel, ForwardRulesDetailModel, ForwardRulesDetailDeleteModel
from module_hrm.utils.util import PermissionHandler
from utils.common_util import CamelCaseUtil
from utils.page_util import PageUtil


class ForwardRulesDao:
    """
    转发或代理规则
    """

    @classmethod
    def get_by_id(cls, db: Session, rule_id: int) -> QtrForwardRules:
        """
        根据规则id获取规则详情

        """
        info = db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == rule_id).first()

        return info

    @classmethod
    def get_by_ids(cls, db: Session, rule_ids: list[int]) -> list[QtrForwardRules]:
        """
        根据规则id获取规则详情

        """
        info = db.query(QtrForwardRules).filter(QtrForwardRules.rule_id.in_(rule_ids)).all()

        return info

    @classmethod
    def get_list_by_page(cls, db: Session, query_object: ForwardRulesQueryModel, data_scope_sql:str, is_page=True):
        query = db.query(QtrForwardRules).filter(eval(data_scope_sql))

        if query_object.only_self:
            query = query.filter(QtrForwardRules.manager == query_object.manager)

        if query_object.rule_id:
            query = query.filter(QtrForwardRules.rule_id == query_object.rule_id)

        if query_object.status:
            query = query.filter(QtrForwardRules.status == query_object.status)

        if query_object.origin_url:
            query = query.filter(QtrForwardRules.origin_url.like(f'%{query_object.rule_name}%'))
        if query_object.target_url:
            query = query.filter(QtrForwardRules.target_url.like(f'%{query_object.rule_name}%'))

        if query_object.rule_name:
            query = query.filter(QtrForwardRules.rule_name.like(f'%{query_object.rule_name}%'))

        # 添加排序条件
        query = query.order_by(QtrForwardRules.create_time.desc()).order_by(QtrForwardRules.order_num).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def get_list_all(cls, db: Session, data_scope_sql: str) -> list[ForwardRulesModel]:
        query = db.query(QtrForwardRules).filter(eval(data_scope_sql))
        all_data_orm = query.order_by(QtrForwardRules.create_time.desc()).order_by(
            QtrForwardRules.order_num).distinct().all()
        all_data = CamelCaseUtil.transform_result(all_data_orm)

        return all_data

    @classmethod
    def create(cls, db: Session, data: ForwardRulesModel):
        if isinstance(data, ForwardRulesModelForApi):
            data = ForwardRulesModel(**data.model_dump(exclude_unset=True, by_alias=True))
        data_dict = data.model_dump(exclude_unset=True)
        db_case = QtrForwardRules(**data_dict)
        db.add(db_case)
        db.flush()

    @classmethod
    def update(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel = None):
        if isinstance(data, ForwardRulesModelForApi):
            data = ForwardRulesModel(**data.model_dump(exclude_unset=True, by_alias=True))

        PermissionHandler.check_is_self(user, db.query(QtrForwardRules).filter(
            QtrForwardRules.rule_id == data.rule_id).first())

        data_dict = data.model_dump(exclude_unset=True)
        data_dict.pop('rule_id')

        db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == data.rule_id).update(data_dict)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesDeleteModel, user: CurrentUserModel = None):
        for rid in data.rule_id:
            PermissionHandler.check_is_self(user, db.query(QtrForwardRules).filter(
                QtrForwardRules.rule_id == rid).first())
            db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == rid).delete()


class ForwardRulesDetailDao:
    """
        转发或代理规则详情
    """

    @classmethod
    def get_by_id(cls, db: Session, data_id: int) -> QtrForwardRulesDetail | None:
        """
        根据规则id获取规则详情

        """
        info = db.query(QtrForwardRulesDetail).filter(QtrForwardRulesDetail.rule_detail_id == data_id).first()

        return info

    @classmethod
    def get_by_rule_ids(cls, db: Session, rule_ids: list[int]) -> list[QtrForwardRulesDetail]:
        """
        根据规则id获取规则详情

        """
        info = db.query(QtrForwardRulesDetail).filter(QtrForwardRulesDetail.rule_id.in_(rule_ids)).all()

        return info

    @classmethod
    def get_list_by_page(cls, db: Session, query_object: ForwardRulesDetailQueryModel, data_scope_sql:str|None = None, is_page=True):
        query = db.query(QtrForwardRulesDetail)
        if data_scope_sql:
            query = query.filter(eval(data_scope_sql))

        if query_object.rule_id:
            query = query.filter(QtrForwardRulesDetail.rule_id == query_object.rule_id)

        if query_object.status:
            query = query.filter(QtrForwardRulesDetail.status == query_object.status)

        if query_object.origin_url:
            query = query.filter(QtrForwardRulesDetail.origin_url.like(f'%{query_object.origin_url}%'))
        if query_object.target_url:
            query = query.filter(QtrForwardRulesDetail.target_url.like(f'%{query_object.target_url}%'))

        if query_object.rule_detail_name:
            query = query.filter(QtrForwardRulesDetail.rule_detail_name.like(f'%{query_object.rule_detail_name}%'))

        # 添加排序条件
        query = query.order_by(QtrForwardRulesDetail.create_time.desc()).order_by(
            QtrForwardRulesDetail.order_num).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def get_list_all(cls, db: Session) -> list[ForwardRulesDetailModel]:
        query = db.query(QtrForwardRulesDetail)
        all_data_orm = query.order_by(QtrForwardRulesDetail.create_time.desc()).order_by(
            QtrForwardRulesDetail.order_num).distinct().all()
        all_data = CamelCaseUtil.transform_result(all_data_orm)

        return all_data

    @classmethod
    def create(cls, db: Session, data: ForwardRulesDetailModel):
        data_dict = data.model_dump(exclude_unset=True)
        db_case = QtrForwardRulesDetail(**data_dict)
        db.add(db_case)
        db.flush()
        db.commit()

    @classmethod
    def update(cls, db: Session, data: ForwardRulesDetailModel, user: CurrentUserModel = None):
        PermissionHandler.check_is_self(user, db.query(QtrForwardRulesDetail).filter(
            QtrForwardRulesDetail.rule_id == data.rule_id).first())

        data_dict = data.model_dump(exclude_unset=True)

        db.query(QtrForwardRulesDetail).filter(QtrForwardRulesDetail.rule_detail_id == data.rule_detail_id).update(data_dict)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesDetailDeleteModel, user: CurrentUserModel = None):
        for rid in data.rule_detail_id:
            PermissionHandler.check_is_self(user, db.query(QtrForwardRulesDetail).filter(
                QtrForwardRulesDetail.rule_detail_id == rid).first())
            db.query(QtrForwardRulesDetail).filter(QtrForwardRulesDetail.rule_detail_id == rid).delete()

        for rid in data.rule_id:
            PermissionHandler.check_is_self(user, db.query(QtrForwardRulesDetail).filter(
                QtrForwardRulesDetail.rule_id == rid).first())
            db.query(QtrForwardRulesDetail).filter(QtrForwardRulesDetail.rule_id == rid).delete()
