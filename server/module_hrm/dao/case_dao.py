from sqlalchemy.orm import Session

from module_hrm.entity.do.case_do import HrmCase, HrmCaseModuleProject
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import *
from module_hrm.enums.enums import DataType
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
        query = db.query(HrmCase,
                         HrmProject.project_name,
                         HrmModule.module_name
                         ).outerjoin(HrmProject,
                                HrmCase.project_id == HrmProject.project_id).outerjoin(HrmModule,
                                                                                  HrmCase.module_id == HrmModule.module_id)

        if query_object.type:
            query = query.filter(HrmCase.type == query_object.type)

        # 根据module_id和project_id是否提供来查询
        if query_object.project_id:
            query = query.filter(HrmCase.project_id == query_object.project_id)
        if query_object.module_id:
            query = query.filter(HrmCase.module_id == query_object.module_id)

        # 根据其他查询参数添加过滤条件
        if query_object.case_name:
            query = query.filter(HrmCase.case_name.like(f'%{query_object.case_name}%'))
        if query_object.status is not None:
            query = query.filter(HrmCase.status == query_object.status)
        if query_object.case_id is not None:
            query = query.filter(HrmCase.case_id == query_object.case_id)

        # 添加排序条件
        query = query.order_by(HrmCase.create_time.desc()).order_by(HrmCase.sort).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def add_case_dao(cls, db: Session, case: CaseModel | CaseModelForApi):
        """
        新增用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        if not isinstance(case, CaseModel):
            case = CaseModel(**case.model_dump(exclude_unset=True))
        db_case = HrmCase(**case.model_dump(exclude_unset=True))
        db.add(db_case)
        db.flush()
        # db.commit()

        return db_case

    @classmethod
    def edit_case_dao(cls, db: Session, case: CaseModel | CaseModelForApi):
        """
        编辑用例数据库操作
        :param db: orm对象
        :param case: 编辑页面获取的CaseModel对象
        :return:
        """
        if not isinstance(case, CaseModel):
            case = CaseModel(**case.model_dump(exclude_unset=True))

        case_data = case.model_dump(exclude_unset=True)
        db.query(HrmCase).filter(HrmCase.case_id == case.case_id).update(case_data)
        case_module_project = {
            'module_id': case.module_id,
            'project_id': case.project_id
        }
        # 更新用例、模块、项目关系表
        db.query(HrmCaseModuleProject).filter(HrmCaseModuleProject.case_id == case.case_id).update(
            case_module_project)

    @classmethod
    def delete_case_dao(cls, db: Session, case: CaseModel):
        """
        删除用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        db.query(HrmCase).filter(HrmCase.case_id == case.case_id).delete()
        # 删除用例、模块、项目关系
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
