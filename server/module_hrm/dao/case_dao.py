from sqlalchemy import and_
from sqlalchemy.orm import Session
from module_hrm.entity.do.case_do import HrmCase, HrmCaseModuleProject
from module_hrm.entity.vo.case_vo import *
from utils.page_util import PageUtil


class CaseDao:
    """
    用例管理数据库操作层
    """

    @classmethod
    def get_case_by_id(cls, db: Session, case_id: int):
        """
        根据用例id获取在用用例详细信息
        :param db: orm对象
        :param case_id: 用例id
        :return: 在用用例信息对象
        """
        info = db.query(HrmCase).filter(HrmCase.case_id == case_id).first()

        return info

    @classmethod
    def get_case_detail_by_info(cls, db: Session, case: CaseQuery):
        """
        根据用例参数获取用例信息
        :param db: orm对象
        :param case: 用例参数对象
        :return: 用例信息对象
        """
        info = db.query(HrmCase) \
            .filter(HrmCase.case_id == case.case_id if case.case_id else True,
                    HrmCase.case_name == case.case_name if case.case_name else True,
                    HrmCase.case_id.in_(db.query(HrmCaseModuleProject.case_id).filter(
                        HrmCaseModuleProject.module_id == case.module_id)) if case.module_id else True,
                    HrmCase.case_id.in_(db.query(HrmCaseModuleProject.case_id).filter(
                        HrmCaseModuleProject.project_id == case.project_id)) if case.project_id else True,
                    HrmCase.sort == case.sort if case.sort else True) \
            .first()

        return info

    @classmethod
    def get_case_list(cls, db: Session, query_object: CasePageQueryModel, is_page: bool = False):
        """
        根据查询参数获取用例列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        # 创建查询的基本部分
        query = db.query(HrmCase)

        # 根据module_id和project_id是否提供来构建子查询条件
        if query_object.module_id is not None and query_object.project_id is not None:
            # 如果两个ID都提供了，添加它们到子查询条件中
            subquery = db.query(HrmCaseModuleProject.case_id).filter(
                and_(
                    HrmCaseModuleProject.module_id == query_object.module_id,
                    HrmCaseModuleProject.project_id == query_object.project_id
                )
            )
            query = query.filter(HrmCase.case_id.in_(subquery))
        elif query_object.module_id is not None:
            subquery = db.query(HrmCaseModuleProject.case_id).filter(
                and_(
                    HrmCaseModuleProject.module_id == query_object.module_id
                )
            )
            query = query.filter(HrmCase.case_id.in_(subquery))
        elif query_object.project_id is not None:
            subquery = db.query(HrmCaseModuleProject.case_id).filter(
                and_(
                    HrmCaseModuleProject.project_id == query_object.project_id
                )
            )
            query = query.filter(HrmCase.case_id.in_(subquery))
        # 根据其他查询参数添加过滤条件
        if query_object.case_name:
            query = query.filter(HrmCase.case_name.like(f'%{query_object.case_name}%'))
        if query_object.status is not None:
            query = query.filter(HrmCase.status == query_object.status)
        if query_object.case_id is not None:
            query = query.filter(HrmCase.case_id == query_object.case_id)

        # 添加排序条件
        query = query.order_by(HrmCase.sort).distinct()

        # query = db.query(HrmCase) \
        #     .filter(HrmCase.case_id.in_(db.query(HrmCaseModuleProject.case_id).filter(
        #     HrmCaseModuleProject.module_id == query_object.module_id & HrmCaseModuleProject.project_id == query_object.project_id)) if query_object.module_id else True,
        #             HrmCase.case_name.like(f'%{query_object.case_name}%') if query_object.case_name else True,
        #             HrmCase.status == query_object.status if query_object.status else True
        #             ) \
        #     .order_by(HrmCase.sort) \
        #     .distinct()
        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def add_case_dao(cls, db: Session, case: CaseModel):
        """
        新增用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        db_case = HrmCase(**case.model_dump())
        db.add(db_case)
        db.flush()

        return db_case

    @classmethod
    def edit_case_dao(cls, db: Session, case: dict):
        """
        编辑用例数据库操作
        :param db: orm对象
        :param case: 需要更新的用例字典
        :return:
        """
        db.query(HrmCase).filter(HrmCase.case_id == case.get('case_id')).update(case)
        db.query(HrmCaseModuleProject).filter(HrmCaseModuleProject.case_id == case.get('case_id')).update(case)

    @classmethod
    def delete_case_dao(cls, db: Session, case: CaseModel):
        """
        删除用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        db.query(HrmCase).filter(HrmCase.case_id == case.case_id).delete()
        db.query(HrmCaseModuleProject).filter(HrmCaseModuleProject.case_id == case.case_id).delete()

    @classmethod
    def add_case_module_project_dao(cls, db: Session, case_project: CaseModuleProjectModel):
        """
        新增用例、模块、项目关联信息数据库操作
        :param db: orm对象
        :param case_project: 用例和项目关联对象
        :return:
        """
        db_case_module_project = HrmCaseModuleProject(**case_project.model_dump())
        db.add(db_case_module_project)