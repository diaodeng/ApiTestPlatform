from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.forward_rules_do import QtrForwardRules
from module_hrm.entity.vo.forward_rules_vo import ForwardRulesModel
from module_hrm.utils.util import PermissionHandler
from utils.common_util import CamelCaseUtil
from utils.page_util import PageUtil


class ForwardRulesDao:
    """
    转发或代理规则
    """

    @classmethod
    def get_by_id(cls, db: Session, rule_id: int):
        """
        根据规则id获取规则详情

        """
        info = db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == rule_id).first()

        return info

    @classmethod
    def get_list_by_page(cls, db: Session, query_object: ForwardRulesModel, is_page=True):
        query = db.query(QtrForwardRules)

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
    def get_list_all(cls, db: Session) -> list[ForwardRulesModel]:
        query = db.query(QtrForwardRules)
        all_data_orm = query.order_by(QtrForwardRules.create_time.desc()).order_by(
            QtrForwardRules.order_num).distinct().all()
        all_data = CamelCaseUtil.transform_result(all_data_orm)

        return all_data

    @classmethod
    def create(cls, db: Session, data: ForwardRulesModel):
        if not isinstance(data, ForwardRulesModel):
            data = ForwardRulesModel(**data.model_dump(exclude_unset=True, by_alias=True))
        data_dict = data.model_dump(exclude_unset=True)
        db_case = QtrForwardRules(**data_dict)
        db.add(db_case)
        db.flush()

    @classmethod
    def update(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel = None):
        if not isinstance(data, ForwardRulesModel):
            data = ForwardRulesModel(**data.model_dump(exclude_unset=True, by_alias=True))

        data = data.model_dump(exclude_unset=True)
        PermissionHandler.check_is_self(user, db.query(QtrForwardRules).filter(
            QtrForwardRules.rule_id == data.rule_id).first())

        db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == data.rule_id).update(data)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel = None):
        PermissionHandler.check_is_self(user, db.query(QtrForwardRules).filter(
            QtrForwardRules.rule_id == data.rule_id).first())
        db.query(QtrForwardRules).filter(QtrForwardRules.rule_id == data.case_id).delete()
