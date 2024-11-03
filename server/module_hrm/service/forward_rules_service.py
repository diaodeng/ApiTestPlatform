from module_admin.entity.vo.user_vo import CurrentUserModel, UserModel
from module_hrm.dao.forward_rules_dao import ForwardRulesDao, ForwardRulesDetailDao
from module_hrm.entity.dto.forward_rules_dto import ForwardRulesModelForApi
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.forward_rules_vo import ForwardRulesModel, ForwardRulesQueryModel, ForwardRulesDeleteModel, \
    ForwardRulesDetailModel, ForwardRulesDetailQueryModel, ForwardRulesDetailDeleteModel
from utils.common_util import export_list2excel, CamelCaseUtil
from utils.page_util import PageResponseModel
from sqlalchemy.orm import Session


class ForwardRulesService:
    @classmethod
    def add(cls, db: Session, data: ForwardRulesModel):
        ForwardRulesDao.create(db, data)

    @classmethod
    def copy(cls, db: Session, data_info: ForwardRulesModel, user: CurrentUserModel):
        old_data_obj = cls.detail(db, data_info.rule_id)
        del old_data_obj.id
        del old_data_obj.create_time
        del old_data_obj.update_time
        del old_data_obj.rule_id
        old_data_obj.rule_name = data_info.rule_name
        old_data_obj.manager = user.user.user_id
        old_data_obj.create_by = user.user.user_name
        old_data_obj.update_by = user.user.user_name
        ForwardRulesDao.create(db, old_data_obj)

    @classmethod
    def update(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel):
        ForwardRulesDao.update(db, data, user)

    @classmethod
    def detail(cls, db: Session, data_id: int) -> ForwardRulesModel:
        data = ForwardRulesDao.get_by_id(db, data_id)
        data_dict = CamelCaseUtil.transform_result(data)
        data = ForwardRulesModelForApi(**data_dict)
        # data = ForwardRulesModelForApi.model_validate(data)
        return data

    @classmethod
    def batch_detail(cls, db: Session, data_ids: list[int]) -> list[ForwardRulesModelForApi]:
        datas_orm = ForwardRulesDao.get_by_ids(db, data_ids)
        datas = [ForwardRulesModelForApi.model_validate(data) for data in datas_orm]
        return datas

    @classmethod
    def query_all(cls, db: Session) -> list[ForwardRulesModel]:
        return ForwardRulesDao.get_list_all(db)

    @classmethod
    def query_list(cls, db: Session, query_info: ForwardRulesQueryModel) -> list[ForwardRulesModel]:
        return ForwardRulesDao.get_list_by_page(db, query_info)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesDeleteModel, user: CurrentUserModel):
        ForwardRulesDao.delete(db, data, user)
        ForwardRulesDetailService.delete(db, ForwardRulesDetailDeleteModel(rule_id=data.rule_id), user)

    @classmethod
    def change_status(cls, db: Session, data: ForwardRulesModel, user: CurrentUserModel):
        ForwardRulesDao.update(db, data, user)

    @classmethod
    def get_forward_rules_for_run(cls, db: Session, data_ids: list[int]) -> dict[str, str]:
        rules = {}
        for detail in ForwardRulesDetailService.detail_by_rule_id(db, data_ids):
            for t_url in detail.origin_url:
                rules[t_url] = detail.target_url
        return rules


class ForwardRulesDetailService:
    @classmethod
    def add(cls, db: Session, data: ForwardRulesDetailModel):
        ForwardRulesDetailDao.create(db, data)

    @classmethod
    def copy(cls, db: Session, data_info: ForwardRulesDetailModel, user: CurrentUserModel):
        old_data_obj = cls.detail(db, data_info.rule_detail_id)
        del old_data_obj.id
        del old_data_obj.create_time
        del old_data_obj.update_time
        del old_data_obj.rule_detail_id
        old_data_obj.rule_detail_name = data_info.rule_detail_name
        old_data_obj.manager = user.user.user_id
        old_data_obj.create_by = user.user.user_name
        old_data_obj.update_by = user.user.user_name
        ForwardRulesDetailDao.create(db, old_data_obj)

    @classmethod
    def update(cls, db: Session, data: ForwardRulesDetailModel, user: CurrentUserModel):
        ForwardRulesDetailDao.update(db, data, user)

    @classmethod
    def detail(cls, db: Session, data_id: int) -> ForwardRulesDetailModel:
        data = ForwardRulesDetailDao.get_by_id(db, data_id)
        data = ForwardRulesDetailModel(**CamelCaseUtil.transform_result(data))
        return data

    @classmethod
    def detail_by_rule_id(cls, db: Session, rule_ids: list[int]) -> list[ForwardRulesDetailModel]:
        datas_orm = ForwardRulesDetailDao.get_by_rule_ids(db, rule_ids)
        datas = [ForwardRulesDetailModel.model_validate(data) for data in datas_orm]
        return datas

    @classmethod
    def query_list(cls, db: Session, query_info: ForwardRulesDetailQueryModel) -> list[ForwardRulesDetailModel]:
        return ForwardRulesDetailDao.get_list_by_page(db, query_info)

    @classmethod
    def delete(cls, db: Session, data: ForwardRulesDetailDeleteModel, user: CurrentUserModel):
        ForwardRulesDetailDao.delete(db, data, user)

    @classmethod
    def change_status(cls, db: Session, data: ForwardRulesDetailModel, user: CurrentUserModel):
        ForwardRulesDetailDao.update(db, data, user)
