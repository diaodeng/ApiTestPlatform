from sqlalchemy.orm import Session
from module_hrm.entity.do.suite_do import QtrSuite, QtrSuiteDetail
from module_hrm.entity.vo.suite_vo import *
from utils.time_format_util import list_format_datetime


class SuiteDao:
    """
    测试套件模块数据库操作层
    """

    @classmethod
    def get_suite_by_id(cls, db: Session, suite_id: int):
        """
        根据套件id获取套件信息
        :param db: orm对象
        :param suite_id: 套件id
        :return: 套件信息对象
        """
        suite_info = db.query(QtrSuite) \
            .filter(QtrSuite.suite_id == suite_id,
                    QtrSuite.del_flag == 0) \
            .first()

        return suite_info


    @classmethod
    def get_suite_list(cls, db: Session, page_object: SuiteModel, data_scope_sql: str):
        """
        根据查询参数获取套件列表信息
        :param db: orm对象
        :param page_object: 不分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 套件列表信息对象
        """
        suite_result = db.query(QtrSuite) \
            .filter(QtrSuite.del_flag == 0,
                    QtrSuite.status == page_object.status if page_object.status else True,
                    QtrSuite.suite_name.like(f'%{page_object.suite_name}%') if page_object.suite_name else True,
                    eval(data_scope_sql)) \
            .order_by(QtrSuite.order_num) \
            .distinct().all()

        return suite_result


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
    def delete_suite_dao(cls, db: Session, suite: SuiteModel):
        """
        删除测试套件数据库操作
        :param db: orm对象
        :param suite: 测试套件对象
        :return:
        """
        (db.query(QtrSuite).filter(QtrSuite.suite_id == suite.suite_id)
         .update({QtrSuite.del_flag: '2', QtrSuite.update_by: suite.update_by, QtrSuite.update_time: suite.update_time}))

    @classmethod
    def get_suite_detail_by_id(cls, db: Session, suite_id: int):
        """
        根据套件id获取套件详细信息
        :param db: orm对象
        :param suite_id: 套件id
        :return: 套件详情对象
        """
        suite_details = db.query(QtrSuiteDetail) \
            .filter(QtrSuiteDetail.suite_id == suite_id,
                    QtrSuiteDetail.del_flag == 0).first()

        return suite_details
