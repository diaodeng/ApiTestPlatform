from fastapi import APIRouter, Request
from fastapi import Depends
from config.get_db import get_db
from sqlalchemy.orm import Session
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.service.project_service import ProjectService, ProjectModel, ProjectQueryModel, DeleteProjectModel
from module_hrm.service.debugtalk_service import DebugTalkService, DeleteDebugTalkModel
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil
from utils.log_util import logger
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.aspect.data_scope import GetDataScope
from module_admin.annotation.log_annotation import log_decorator
from utils.snowflake import snowIdWorker
from datetime import datetime

projectController = APIRouter(prefix='/hrm/project', dependencies=[Depends(LoginService.get_current_user)])


@projectController.get("/list", response_model=list[ProjectModel] | PageResponseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:list'))])
async def get_hrm_project_list(request: Request,
                               query: ProjectQueryModel = Depends(ProjectQueryModel.as_query),
                               query_db: Session = Depends(get_db),
                               data_scope_sql: str = Depends(GetDataScope('HrmProject', user_alias='manager'))):
    try:
        query_result = ProjectService.get_project_list_services(query_db, query, data_scope_sql)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        else:
            return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@projectController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:add'))])
@log_decorator(title='项目管理', business_type=1)
async def add_hrm_project(request: Request,
                          add_project: ProjectModel,
                          query_db: Session = Depends(get_db),
                          current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_project.manager = current_user.user.user_id
        add_project.create_by = current_user.user.user_name
        add_project.update_by = current_user.user.user_name
        add_project.dept_id = current_user.user.dept_id
        add_project.project_id = snowIdWorker.get_id()
        add_project_result = ProjectService.add_project_services(query_db, add_project)
        if add_project_result.is_success:
            logger.info(add_project_result.message)
            return ResponseUtil.success(data=add_project_result)
        else:
            logger.warning(add_project_result.message)
            return ResponseUtil.failure(msg=add_project_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@projectController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:edit'))])
@log_decorator(title='项目管理', business_type=2)
async def edit_hrm_project(request: Request,
                           edit_project: ProjectModel,
                           query_db: Session = Depends(get_db),
                           current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_project.update_by = current_user.user.user_name
        edit_project.update_time = datetime.now()
        edit_project_result = ProjectService.edit_project_services(query_db, edit_project)
        if edit_project_result.is_success:
            logger.info(edit_project_result.message)
            return ResponseUtil.success(msg=edit_project_result.message)
        else:
            logger.warning(edit_project_result.message)
            return ResponseUtil.failure(msg=edit_project_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@projectController.delete("/{project_ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:project:remove'))])
@log_decorator(title='项目管理', business_type=3)
async def delete_hrm_project(request: Request, project_ids: str, query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        delete_project = DeleteProjectModel(projectIds=project_ids)
        delete_project.update_by = current_user.user.user_name
        delete_project.update_time = datetime.now()
        delete_project_result = ProjectService.delete_project_services(query_db, delete_project)

        delete_debugtalk = DeleteDebugTalkModel(projectIds=project_ids)
        delete_debugtalk.update_by = current_user.user.user_name
        delete_debugtalk.update_time = datetime.now()
        delete_debugtalk_result = DebugTalkService.delete_debugtalk_services(query_db, delete_debugtalk)
        if delete_project_result.is_success and delete_debugtalk_result.is_success:
            logger.info(delete_project_result.message)
            return ResponseUtil.success(msg=delete_project_result.message)
        else:
            logger.warning(delete_project_result.message)
            return ResponseUtil.failure(msg=delete_project_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@projectController.get("/{project_id}", response_model=ProjectModel,
                       dependencies=[
                           Depends(CheckUserInterfaceAuth(['hrm:project:detail', "hrm:project:edit"], False))])
async def query_detail_system_project(request: Request, project_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_project_result = ProjectService.project_detail_services(query_db, project_id)
        logger.info(f'获取project_id为{project_id}的信息成功')
        return ResponseUtil.success(data=detail_project_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
