from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.suite_do import QtrSuite, QtrSuiteDetail
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.vo.suite_vo import *
from module_hrm.utils.util import PermissionHandler
from utils.page_util import PageUtil
from module_hrm.enums.enums import DataType


class SuiteDao:
    """
    测试套件模块数据库操作层
    """

    @classmethod
    def get_suite_by_id(cls, db: Session, suite_id: int):
        """
        根据套件id获取套件信息
        :param db: orm对象
        :param suite_detail_id: 套件详情id
        :return: 套件信息对象
        """
        suite_info = db.query(QtrSuite) \
            .filter(QtrSuite.suite_id == suite_id,
                    QtrSuite.del_flag == 0) \
            .first()

        return suite_info

    @classmethod
    def get_suite_list(cls, db: Session, page_object: SuitePageQueryModel, data_scope_sql: str, is_page: bool = False):
        """
        根据查询参数获取套件列表信息
        :param db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :param is_page: 是否开启分页
        :return: 套件列表信息对象
        """
        suite_result = db.query(QtrSuite) \
            .filter(QtrSuite.del_flag == 0,
                    QtrSuite.status == page_object.status if page_object.status else True,
                    QtrSuite.suite_name.like(f'%{page_object.suite_name}%') if page_object.suite_name else True,
                    eval(data_scope_sql))
        if page_object.only_self:
            suite_result = suite_result.filter(QtrSuite.manager == page_object.manager)
        suite_result = suite_result.order_by(QtrSuite.order_num, QtrSuite.create_time.desc(),QtrSuite.update_time.desc()) \
            .distinct()
        suite_list = PageUtil.paginate(suite_result, page_object.page_num, page_object.page_size, is_page)

        return suite_list

    @classmethod
    def get_suite_by_info(cls, db: Session, suite: SuiteModel):
        """
        根据参数获取套件信息
        :param db: orm对象
        :param suite: 套件参数对象
        :return: 套件信息对象
        """
        suite_info = db.query(QtrSuite) \
            .filter(QtrSuite.suite_name == suite.suite_name if suite.suite_name else True) \
            .first()
        return suite_info

    @classmethod
    def add_suite_dao(cls, db: Session, suite: SuiteModel):
        """
        新增测试套件数据库操作
        :param db: orm对象
        :param suite: 套件对象
        :return: 新增校验结果
        """
        db_suite = QtrSuite(**suite.model_dump())
        db.add(db_suite)
        db.flush()

        return db_suite

    @classmethod
    def edit_suite_dao(cls, db: Session, suite: dict):
        """
        编辑测试套件数据库操作
        :param db: orm对象
        :param suite: 需要更新的测试套件字典
        :return: 编辑校验结果
        """
        db.query(QtrSuite) \
            .filter(QtrSuite.suite_id == suite.get('suite_id')) \
            .update(suite)

    @classmethod
    def delete_suite_dao(cls, db: Session, suite: SuiteModel, user: CurrentUserModel = None):
        """
        删除测试套件数据库操作
        :param db: orm对象
        :param suite: 测试套件对象
        :return:
        """
        PermissionHandler.check_is_self(user, db.query(QtrSuite).filter(QtrSuite.suite_id == suite.suite_id).first())
        # 硬删除
        db.query(QtrSuite).filter(QtrSuite.suite_id == suite.suite_id).delete()
        # (db.query(QtrSuite).filter(QtrSuite.suite_id == suite.suite_id)
        # .update(
        #     {QtrSuite.del_flag: '2', QtrSuite.update_by: suite.update_by, QtrSuite.update_time: suite.update_time}))


class SuiteDetailDao:
    """
    测试套件详情模块数据库操作层
    """

    @classmethod
    def get_suite_detail_list_by_suite_id_dao(cls, db: Session, query_obj: dict):
        """
        根据套件配置信息获取套件数据ID列表
        :param db: orm对象
        :param query_obj: 查询条件
        :return: 套件数据ID列表
        """
        suite_detail_list = db.query(QtrSuiteDetail.data_id).filter(QtrSuiteDetail.del_flag == 0,
                                                                    QtrSuiteDetail.suite_id == query_obj.get(
                                                                        'suite_id'),
                                                                    QtrSuiteDetail.data_type == query_obj.get(
                                                                        'data_type')
                                                                    ).distinct().all()
        return suite_detail_list

    @classmethod
    def get_suite_detail_list_dao(cls, db: Session, query_object: SuiteDetailPageQueryModel, data_scope_sql: str,
                                  is_page: bool = False):
        """
        根据条件获取套件详细信息列表
        :param db: orm对象
        :param query_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :param is_page: 是否开启分页
        :return: 套件详细信息对象列表
        """
        print("###############", DataType.case.value, QtrSuiteDetail.data_id)
        query = db.query(QtrSuiteDetail,
                         HrmCase.status.label("caseStatus"),
                         HrmProject.status.label("projectStatus"),
                         HrmModule.status.label("moduleStatus"),
                         HrmCase.case_id,
                         HrmProject.project_id,
                         HrmModule.module_id,
                         HrmCase.case_name,
                         HrmProject.project_name,
                         HrmModule.module_name
                         ).outerjoin(HrmCase, (QtrSuiteDetail.data_id == HrmCase.case_id) & (
                QtrSuiteDetail.data_type == DataType.case.value)
                                     ).outerjoin(HrmProject, (QtrSuiteDetail.data_id == HrmProject.project_id) & (
                QtrSuiteDetail.data_type == DataType.project.value)
                                                 ).outerjoin(HrmModule,
                                                             (QtrSuiteDetail.data_id == HrmModule.module_id) & (
                                                                     QtrSuiteDetail.data_type == DataType.module.value))

        query = query.filter(QtrSuiteDetail.suite_id == query_object.suite_id, QtrSuiteDetail.del_flag == 0)
        if query_object.status:
            query = query.filter(or_(HrmCase.status == query_object.status,
                                     HrmModule.status == query_object.status,
                                     HrmProject.status == query_object.status))

        query = query.filter(eval(data_scope_sql))
        query = query.filter(QtrSuiteDetail.data_id == query_object.data_id if query_object.data_id else True)

        # query = query.filter(HrmCase.case_name == query_object.data_name if query_object.data_name else True)

        if query_object.only_self:
            query = query.filter(QtrSuiteDetail.manager == query_object.manager)
        # 添加排序条件
        query = query.order_by(QtrSuiteDetail.order_num, QtrSuiteDetail.create_time.desc()).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)
        return post_list

    @classmethod
    def get_suite_detail_by_id(cls, db: Session, suite_detail_id: int):
        """
        根据套件详细id获取套件详细信息
        :param db: orm对象
        :param suite_id: 套件详细id
        :return: 套件详情对象
        """
        suite_details = db.query(QtrSuiteDetail) \
            .filter(QtrSuiteDetail.suite_detail_id == suite_detail_id,
                    QtrSuiteDetail.del_flag == 0).first()

        return suite_details

    @classmethod
    def add_suite_detail_dao(cls, db: Session, suite_details: list[SuiteDetailModel]):
        """
        新增测试套件数据库操作
        :param db: orm对象
        :param suite_details: 套件详情对象列表
        :return: 新增校验结果
        """
        db_suite_details = [QtrSuiteDetail(**suite_detail.model_dump()) for suite_detail in suite_details]
        db.bulk_save_objects(db_suite_details)
        db.flush()

        return db_suite_details

    @classmethod
    def edit_suite_detail_status_by_id(cls, db: Session, suite_detail: dict):
        """
        根据套件详细id班级套件详细信息
        :param db: orm对象
        :param suite_id: 套件详细id
        :return: 套件详情对象
        """
        db.query(QtrSuiteDetail) \
            .filter(QtrSuiteDetail.suite_detail_id == suite_detail.get('suite_detail_id')) \
            .update(suite_detail)

    @classmethod
    def del_suite_detail_by_id(cls, db: Session, detail_id):
        db.query(QtrSuiteDetail).filter(QtrSuiteDetail.suite_detail_id == detail_id).delete()
