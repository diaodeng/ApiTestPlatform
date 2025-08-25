from sqlalchemy import update
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.suite_dao import SuiteDao, SuiteDetailDao
from module_hrm.entity.do.suite_do import QtrSuiteDetail
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.suite_vo import SuiteModel, SuitePageQueryModel, DeleteSuiteModel, SuiteDetailModel, \
    SuiteDetailPageQueryModel
from utils.common_util import CamelCaseUtil
from utils.page_util import PageResponseModel


class SuiteService:
    """
    测试套件模块服务层
    """

    @classmethod
    def get_suite_services(cls, query_db: Session, suite_id: int):
        """
        获取测试套件信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 测试套件信息对象
        """
        suite_result = SuiteDao.get_suite_by_id(query_db, suite_id)
        result = SuiteModel(**CamelCaseUtil.transform_result(suite_result))
        return result

    @classmethod
    def get_suite_list_services(cls, query_db: Session, page_object: SuitePageQueryModel, data_scope_sql: str,
                                is_page: bool = False):
        """
        获取测试套件列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 测试套件列表信息对象
        """
        suite_list_result = SuiteDao.get_suite_list(query_db, page_object, data_scope_sql, is_page)

        return suite_list_result

    @classmethod
    def add_suite_services(cls, query_db: Session, page_object: SuiteModel):
        """
        新增测试套件信息service
        :param query_db: orm对象
        :param page_object: 新增测试套件对象
        :return: 新增测试套件校验结果
        """
        suite = SuiteDao.get_suite_by_info(query_db, SuiteModel(suiteName=page_object.suite_name))
        if suite:
            result = dict(is_success=False, message='套件名称已存在')
        else:
            try:
                SuiteDao.add_suite_dao(query_db, page_object)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_suite_services(cls, query_db: Session, suite_object: SuiteModel):
        """
        编辑测试套件信息service
        :param query_db: orm对象
        :param suite_object: 编辑测试套件对象
        :return: 编辑测试套件校验结果
        """
        edit_suite = suite_object.model_dump(exclude_unset=True)
        suite_info = cls.get_suite_services(query_db, edit_suite.get('suite_id'))
        if suite_info:
            if suite_info.suite_name != suite_object.suite_name:
                suite = SuiteDao.get_suite_by_info(query_db, SuiteModel(suiteName=suite_object.suite_name))
                if suite:
                    result = dict(is_success=False, message='测试套件名称不能重复')
                    return CrudResponseModel(**result)
            try:
                SuiteDao.edit_suite_dao(query_db, edit_suite)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='测试套件不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_suite_services(cls, query_db: Session, page_object: DeleteSuiteModel, user: CurrentUserModel = None):
        """
        删除测试套件信息service
        :param query_db: orm对象
        :param page_object: 删除测试套件对象
        :return: 删除测试套件校验结果
        """
        if page_object.suite_ids.split(','):
            suite_id_list = page_object.suite_ids.split(',')
            try:
                for suite_id in suite_id_list:
                    SuiteDao.delete_suite_dao(query_db, SuiteModel(suiteId=suite_id), user)
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入测试套件id为空')
        return CrudResponseModel(**result)


class SuiteDetailService:
    """
    测试套件详情模块服务层
    """

    @classmethod
    def get_suite_detail_services(cls, query_db: Session, suite_detail_id: int):
        """
        获取测试套件信息service
        :param query_db: orm对象
        :param page_object: 查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 测试套件信息对象
        """
        suite_result = SuiteDetailDao.get_suite_detail_by_id(query_db, suite_detail_id)
        result = SuiteDetailModel(**CamelCaseUtil.transform_result(suite_result))
        return result

    @classmethod
    def get_suite_detail_list_services(cls, query_db: Session, page_object: SuiteDetailPageQueryModel,
                                       data_scope_sql: str,
                                       is_page: bool = False):
        """
        获取测试套件列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 测试套件详细列表信息对象
        """

        def calc_value(name, datas: list):
            result = None
            for data in datas:
                val = list(data.values())
                if val and val[0]:
                    result = {name: val[0]}

            if result is None:
                result = {name: ""}
            return result

        suite_detail_list_result = SuiteDetailDao.get_suite_detail_list_dao(query_db, page_object, data_scope_sql,
                                                                            is_page)
        list_result = PageResponseModel(
            **{
                **suite_detail_list_result.model_dump(by_alias=True),
                'rows': [{**row[0],
                          **calc_value("dataStatus", row[1:4]),
                          **calc_value("dataId", row[4:7]),
                          **calc_value("dataName", row[7:10]),
                          } for row in suite_detail_list_result.rows]
            }
        )

        return list_result

    @classmethod
    def add_suite_detail_services(cls, query_db: Session, page_objects: list[SuiteDetailModel]):
        """
        新增测试套件详细信息service
        :param query_db: orm对象
        :param page_objects: 新增测试套件详细对象列表
        :return: 新增测试套件校验结果
        """
        # TODO 根据data_id + data_type去重
        # suite = SuiteDao.get_suite_by_info(query_db, SuiteModel(suiteName=page_object.suite_name))
        # if suite:
        #     result = dict(is_success=False, message='套件名称已存在')
        # else:
        try:
            SuiteDetailDao.add_suite_detail_dao(query_db, page_objects)
            query_db.commit()
            result = dict(is_success=True, message='新增成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_suite_detail_services(cls, query_db: Session, suite_detail_object: SuiteDetailModel):
        """
        编辑测试套件详细信息service
        :param query_db: orm对象
        :param suite_object: 编辑测试套件详细对象
        :return: 编辑测试套件详细校验结果
        """
        edit_suite_detail = suite_detail_object.model_dump(exclude_unset=True)
        suite_info = cls.get_suite_detail_services(query_db, edit_suite_detail.get('suite_detail_id'))
        if suite_info:
            try:
                SuiteDetailDao.edit_suite_detail_status_by_id(query_db, edit_suite_detail)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='数据不存在')

        return CrudResponseModel(**result)

    @classmethod
    def change_detail_order(cls, query_db: Session, suite_detail_object: SuiteDetailModel):
        """
        编辑测试套件详细信息service
        :param query_db: orm对象
        :param suite_object: 编辑测试套件详细对象
        :return: 编辑测试套件详细校验结果
        """
        new_order = suite_detail_object.order_num
        current_data_sql_obj = query_db.query(QtrSuiteDetail).filter(
            QtrSuiteDetail.suite_id == suite_detail_object.suite_id,
            QtrSuiteDetail.data_id == suite_detail_object.data_id).first()
        old_older = current_data_sql_obj.order_num

        if new_order > old_older:
            update_sql = update(QtrSuiteDetail).where(QtrSuiteDetail.suite_id == suite_detail_object.suite_id).where(
                QtrSuiteDetail.order_num > old_older,
                QtrSuiteDetail.order_num <= new_order).values(order_num=QtrSuiteDetail.order_num - 1,
                                                              update_by=suite_detail_object.update_by,
                                                              update_time=QtrSuiteDetail.update_time,
                                                              )
            query_db.execute(update_sql)
        elif new_order < old_older:
            update_sql = update(QtrSuiteDetail).where(QtrSuiteDetail.suite_id == suite_detail_object.suite_id).where(
                QtrSuiteDetail.order_num < old_older,
                QtrSuiteDetail.order_num >= new_order).values(order_num=QtrSuiteDetail.order_num + 1,
                                                              update_by=suite_detail_object.update_by,
                                                              update_time=QtrSuiteDetail.update_time)
            query_db.execute(update_sql)

        current_data_sql_obj.order_num = new_order
        current_data_sql_obj.update_by = suite_detail_object.update_by
        current_data_sql_obj.update_time = suite_detail_object.update_time
        query_db.commit()

    @classmethod
    def get_suite_detail_list_by_suite_id_services(cls, query_db: Session, query_obj: dict):
        """
        获取套件数据ID列表service
        :param query_db: orm对象
        :param query_obj: 查询条件
        :return: 套件数据ID列表
        """
        suite_detail_list_result = SuiteDetailDao.get_suite_detail_list_by_suite_id_dao(query_db, query_obj)

        return suite_detail_list_result
