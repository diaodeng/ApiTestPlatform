from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.dao.debugtalk_dao import DebugTalkModel
from module_hrm.dao.project_dao import ProjectDao
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.project_vo import DeleteProjectModel, ProjectModel, ProjectQueryModel
from module_hrm.service.debugtalk_service import DebugTalkService
from module_hrm.utils.business_code import ensure_unique_code
from utils.common_util import CamelCaseUtil


class ProjectService:
    """
    椤圭洰绠＄悊妯″潡鏈嶅姟灞?
    """

    @classmethod
    def _resolve_project_code(
        cls,
        query_db: Session,
        project_name: str | None,
        project_code: str | None,
        *,
        current_project_id: int | None = None,
        keep_existing: str | None = None,
    ) -> str:
        incoming_code = str(project_code or "").strip()
        keep_existing_code = str(keep_existing or "").strip()
        if not incoming_code:
            if keep_existing_code:
                return keep_existing_code
            return ""
        existing_codes = {
            str(item[0] or "").strip()
            for item in query_db.query(HrmProject.project_code)
            .filter(HrmProject.project_code.isnot(None))
            .filter(HrmProject.project_code != "")
            .all()
            if str(item[0] or "").strip()
        }
        if current_project_id is not None and keep_existing_code:
            existing_codes.discard(keep_existing_code)
        return ensure_unique_code(incoming_code, existing_codes)

    @classmethod
    def get_project_list_services(
        cls,
        query_db: Session,
        page_object: ProjectQueryModel,
        data_scope_sql: DataScopeExpr,
    ):
        """
        鑾峰彇閮ㄩ」鐩垪琛ㄤ俊鎭痵ervice
        """
        project_list_result = ProjectDao.get_project_list(query_db, page_object, data_scope_sql)
        return project_list_result

    @classmethod
    def add_project_services(cls, query_db: Session, page_object: ProjectModel):
        """
        鏂板椤圭洰淇℃伅service
        """
        project = ProjectDao.get_project_detail_by_info(query_db, ProjectModel(project_name=page_object.project_name))
        if project:
            result = {'is_success': False, 'message': '椤圭洰鍚嶇О宸插瓨鍦?'}
            return CrudResponseModel(**result)

        try:
            incoming_code = str(page_object.project_code or "").strip()
            if incoming_code:
                duplicate = (
                    query_db.query(HrmProject)
                    .filter(HrmProject.project_code == incoming_code)
                    .first()
                )
                if duplicate:
                    return CrudResponseModel(is_success=False, message='椤圭洰涓氬姟缂栫爜宸插瓨鍦?')
                page_object.project_code = incoming_code
            else:
                page_object.project_code = ""
            project = ProjectDao.add_project_dao(query_db, page_object)
            debugtalk = DebugTalkModel()
            debugtalk.project_id = project.project_id
            debugtalk.create_by = project.create_by
            debugtalk.update_by = project.update_by
            debugtalk.create_time = project.create_time
            debugtalk.update_time = project.update_time
            DebugTalkService.add_debugtalk_services(query_db, debugtalk)
            query_db.commit()
            result = {'is_success': True, 'message': '鏂板鎴愬姛'}
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_project_services(cls, query_db: Session, project_object: ProjectModel):
        """
        缂栬緫椤圭洰淇℃伅service
        """
        edit_project = project_object.model_dump(exclude_unset=True)
        project_info = cls.project_detail_services(query_db, edit_project.get('project_id'))
        if project_info:
            if project_info.project_name != project_object.project_name:
                project = ProjectDao.get_project_detail_by_info(
                    query_db,
                    ProjectModel(project_name=project_object.project_name),
                )
                if project:
                    result = {'is_success': False, 'message': '椤圭洰鍚嶇О涓嶈兘閲嶅'}
                    return CrudResponseModel(**result)

            edit_project_code = str(edit_project.get('project_code') or '').strip()
            if edit_project_code:
                duplicate = (
                    query_db.query(HrmProject)
                    .filter(
                        HrmProject.project_code == edit_project_code,
                        HrmProject.project_id != project_info.project_id,
                    )
                    .first()
                )
                if duplicate:
                    return CrudResponseModel(is_success=False, message='椤圭洰涓氬姟缂栫爜宸插瓨鍦?')
            else:
                edit_project['project_code'] = project_info.project_code or ""

            try:
                ProjectDao.edit_project_dao(query_db, edit_project)
                query_db.commit()
                result = {'is_success': True, 'message': '鏇存柊鎴愬姛'}
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = {'is_success': False, 'message': '椤圭洰涓嶅瓨鍦?'}

        return CrudResponseModel(**result)

    @classmethod
    def delete_project_services(cls, query_db: Session, page_object: DeleteProjectModel):
        """
        鍒犻櫎椤圭洰淇℃伅service
        """
        print(page_object.project_ids.split(','))
        if page_object.project_ids.split(','):
            project_id_list = page_object.project_ids.split(',')
            try:
                for project_id in project_id_list:
                    ProjectDao.delete_project_dao(
                        query_db,
                        ProjectModel(projectId=project_id, updateTime=page_object.update_time, updateBy=page_object.update_by),
                    )
                query_db.commit()
                result = {'is_success': True, 'message': '鍒犻櫎鎴愬姛'}
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = {'is_success': False, 'message': '浼犲叆椤圭洰id涓虹┖'}
        return CrudResponseModel(**result)

    @classmethod
    def project_detail_services(cls, query_db: Session, project_id: int):
        """
        鑾峰彇椤圭洰璇︾粏淇℃伅service
        """
        project = ProjectDao.get_project_detail_by_id(query_db, project_id=project_id)
        result = ProjectModel(**CamelCaseUtil.transform_result(project))
        return result
