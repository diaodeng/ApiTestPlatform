from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.project_vo import *
from utils.page_util import PageUtil
from utils.time_format_util import list_format_datetime


class ProjectDao:
    """
    项目管理模块数据库操作层
    """

    @classmethod
    def get_project_by_id(cls, db: Session, project_id: int):
        """
        根据项目id获取在用项目信息
        :param db: orm对象
        :param project_id: 项目id
        :return: 在用项目信息对象
        """
        project_info = db.query(HrmProject)\
            .filter(HrmProject.project_id == project_id,
                    HrmProject.status == 0,
                    HrmProject.del_flag == 0) \
            .first()

        return project_info

    @classmethod
    def get_project_by_id_for_list(cls, db: Session, project_id: int):
        """
        用于获取项目列表的工具方法
        :param db: orm对象
        :param project_id: 项目id
        :return: 项目id对应的信息对象
        """
        project_info = db.query(HrmProject) \
            .filter(HrmProject.project_id == project_id,
                    HrmProject.del_flag == 0) \
            .first()

        return project_info

    @classmethod
    def get_project_detail_by_id(cls, db: Session, project_id: int):
        """
        根据项目id获取项目详细信息
        :param db: orm对象
        :param project_id: 项目id
        :return: 项目信息对象
        """
        project_info = db.query(HrmProject) \
            .filter(HrmProject.project_id == project_id,
                    HrmProject.del_flag == 0) \
            .first()

        return project_info

    @classmethod
    def get_project_detail_by_info(cls, db: Session, project: ProjectModel):
        """
        根据项目参数获取项目信息
        :param db: orm对象
        :param project: 项目参数对象
        :return: 项目信息对象
        """
        project_info = db.query(HrmProject) \
            .filter(HrmProject.project_name == project.project_name if project.project_name else False).first()
        return project_info

    @classmethod
    def get_project_list(cls, db: Session, page_object: ProjectQueryModel, data_scope_sql: str):
        """
        根据查询参数获取项目列表信息
        :param db: orm对象
        :param page_object: 不分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 项目列表信息对象
        """
        project_result = db.query(HrmProject) \
            .filter(HrmProject.del_flag == 0,
                    HrmProject.status == page_object.status if page_object.status else True,
                    HrmProject.project_name.like(f'%{page_object.project_name}%') if page_object.project_name else True,
                    eval(data_scope_sql)) \
            .order_by(HrmProject.order_num, HrmProject.create_time.desc(), HrmProject.update_time.desc()) \
            .distinct()

        post_list = PageUtil.paginate(project_result, page_object.page_num, page_object.page_size, page_object.is_page)

        return post_list

    @classmethod
    def add_project_dao(cls, db: Session, project: ProjectModel):
        """
        新增项目数据库操作
        :param db: orm对象
        :param project: 项目对象
        :return: 新增校验结果
        """
        db_project = HrmProject(**project.model_dump())
        db.add(db_project)
        db.flush()

        return db_project

    @classmethod
    def edit_project_dao(cls, db: Session, project: dict):
        """
        编辑项目数据库操作
        :param db: orm对象
        :param project: 需要更新的项目字典
        :return: 编辑校验结果
        """
        db.query(HrmProject) \
            .filter(HrmProject.project_id == project.get('project_id')) \
            .update(project)

    @classmethod
    def delete_project_dao(cls, db: Session, project: ProjectModel):
        """
        删除项目数据库操作
        :param db: orm对象
        :param project: 项目对象
        :return:
        """
        db.query(HrmProject) \
            .filter(HrmProject.project_id == project.project_id) \
            .update({HrmProject.del_flag: '2', HrmProject.update_by: project.update_by, HrmProject.update_time: project.update_time})
