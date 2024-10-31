from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.forward_rules_dao import ForwardRulesDao
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.forward_rules_vo import ForwardRulesModel
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel
from sqlalchemy.orm import Session


class ForwardRulesService:
    @classmethod
    def add(cls, db: Session, data: ForwardRulesModel):
        ForwardRulesDao.create(db, data)

    @classmethod
    def update(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel):
        ForwardRulesDao.update(db, data, user)

    @classmethod
    def query_all(cls, db: Session) -> list[ForwardRulesModel]:
        return ForwardRulesDao.get_list_all(db)

    @classmethod
    def query_list(cls, db: Session, query_info:ForwardRulesModel) -> list[ForwardRulesModel]:
        return ForwardRulesDao.get_list_by_page(db, query_info)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel):
        ForwardRulesDao.delete(db, data, user)

    @classmethod
    def change_status(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel):
        ForwardRulesDao.update(db, data, user)