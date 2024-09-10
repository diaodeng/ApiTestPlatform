from module_hrm.dao.suite_dao import *
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import CamelCaseUtil


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
    def get_suite_list_services(cls, query_db: Session, page_object: SuitePageQueryModel, data_scope_sql: str, is_page: bool = False):
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
    def delete_suite_services(cls, query_db: Session, page_object: DeleteSuiteModel):
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
                    SuiteDao.delete_suite_dao(query_db, SuiteModel(suiteId=suite_id))
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
    def get_suite_detail_list_services(cls, query_db: Session, page_object: SuiteDetailPageQueryModel, data_scope_sql: str,
                                is_page: bool = False):
        """
        获取测试套件列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 测试套件详细列表信息对象
        """
        suite_detail_list_result = SuiteDetailDao.get_suite_detail_list(query_db, page_object, data_scope_sql, is_page)

        return suite_detail_list_result