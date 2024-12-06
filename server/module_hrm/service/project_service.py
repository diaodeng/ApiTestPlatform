from sqlalchemy.orm import Session

from module_hrm.dao.debugtalk_dao import DebugTalkModel
from module_hrm.dao.project_dao import ProjectDao
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.project_vo import ProjectQueryModel, ProjectModel, DeleteProjectModel
from module_hrm.service.debugtalk_service import DebugTalkService
from utils.common_util import CamelCaseUtil


class ProjectService:
    """
    项目管理模块服务层
    """

    @classmethod
    def get_project_list_services(cls,
                                  query_db: Session,
                                  page_object: ProjectQueryModel,
                                  data_scope_sql: str):
        """
        获取部项目列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: 项目列表信息对象
        """
        project_list_result = ProjectDao.get_project_list(query_db, page_object, data_scope_sql)

        return project_list_result

    @classmethod
    def add_project_services(cls, query_db: Session, page_object: ProjectModel):
        """
        新增项目信息service
        :param query_db: orm对象
        :param page_object: 新增项目对象
        :return: 新增项目校验结果
        """
        project = ProjectDao.get_project_detail_by_info(query_db, ProjectModel(project_name=page_object.project_name))
        if project:
            result = dict(is_success=False, message='项目名称已存在')
        else:
            try:
                project = ProjectDao.add_project_dao(query_db, page_object)
                # belong_project = ProjectDao.get_project_detail_by_info(query_db, page_object)
                debugtalk = DebugTalkModel()
                debugtalk.project_id = project.project_id
                debugtalk.create_by = project.create_by
                debugtalk.update_by = project.update_by
                debugtalk.create_time = project.create_time
                debugtalk.update_time = project.update_time
                DebugTalkService.add_debugtalk_services(query_db, debugtalk)
                query_db.commit()
                result = dict(is_success=True, message='新增成功')
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_project_services(cls, query_db: Session, project_object: ProjectModel):
        """
        编辑项目信息service
        :param query_db: orm对象
        :param project_object: 编辑项目对象
        :return: 编辑项目校验结果
        """
        edit_project = project_object.model_dump(exclude_unset=True)
        project_info = cls.project_detail_services(query_db, edit_project.get('project_id'))
        if project_info:
            if project_info.project_name != project_object.project_name:
                project = ProjectDao.get_project_detail_by_info(query_db,
                                                                ProjectModel(project_name=project_object.project_name))
                if project:
                    result = dict(is_success=False, message='项目名称不能重复')
                    return CrudResponseModel(**result)
            try:
                ProjectDao.edit_project_dao(query_db, edit_project)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='项目不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_project_services(cls, query_db: Session, page_object: DeleteProjectModel):
        """
        删除项目信息service
        :param query_db: orm对象
        :param page_object: 删除项目对象
        :return: 删除项目校验结果
        """
        print(page_object.project_ids.split(','))
        if page_object.project_ids.split(','):
            project_id_list = page_object.project_ids.split(',')
            try:
                for project_id in project_id_list:
                    ProjectDao.delete_project_dao(query_db,
                                                  ProjectModel(projectId=project_id, updateTime=page_object.update_time,
                                                               updateBy=page_object.update_by))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入项目id为空')
        return CrudResponseModel(**result)

    @classmethod
    def project_detail_services(cls, query_db: Session, project_id: int):
        """
        获取项目详细信息service
        :param query_db: orm对象
        :param project_id: 项目id
        :return: 项目id对应的信息
        """
        project = ProjectDao.get_project_detail_by_id(query_db, project_id=project_id)
        result = ProjectModel(**CamelCaseUtil.transform_result(project))

        return result
