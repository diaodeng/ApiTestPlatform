from datetime import datetime

from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.entity.vo.debugtalk_vo import DeleteDebugTalkModel, DebugTalkModel, DebugTalkQueryModel
from module_hrm.service.debugtalk_service import DebugTalkService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil
from utils.snowflake import snowIdWorker

debugtalkController = APIRouter(prefix='/hrm/debugtalk', dependencies=[Depends(LoginService.get_current_user)])


@debugtalkController.get("/list", response_model=list[DebugTalkModel] | PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth('hrm:debugtalk:list'))])
async def get_hrm_debugtalk_list(request: Request,
                                 query: DebugTalkQueryModel = Depends(DebugTalkQueryModel.as_query),
                                 query_db: Session = Depends(get_db),
                                 data_scope_sql: str = Depends(GetDataScope('HrmDebugTalk', user_alias='manager'))):
    try:
        query_result = DebugTalkService.get_debugtalk_list_services(query_db, query, data_scope_sql)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        else:
            return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@debugtalkController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:debugtalk:add'))])
@log_decorator(title='DebugTalk管理', business_type=1)
async def add_hrm_debugtalk(request: Request,
                            add_debugtalk: DebugTalkModel,
                            query_db: Session = Depends(get_db),
                            current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_debugtalk.manager = current_user.user.user_id
        add_debugtalk.create_by = current_user.user.user_name
        add_debugtalk.update_by = current_user.user.user_name
        add_debugtalk.debugtalk_id = snowIdWorker.get_id()
        add_debugtalk.dept_id = current_user.user.dept_id
        add_debugtalk_result = DebugTalkService.add_debugtalk_services(query_db, add_debugtalk)
        if add_debugtalk_result.is_success:
            logger.info(add_debugtalk_result.message)
            return ResponseUtil.success(data=add_debugtalk_result)
        else:
            logger.warning(add_debugtalk_result.message)
            return ResponseUtil.failure(msg=add_debugtalk_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@debugtalkController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:debugtalk:edit'))])
@log_decorator(title='DebugTalk管理', business_type=2)
async def edit_hrm_debugtalk(request: Request,
                             edit_debugtalk: DebugTalkModel,
                             query_db: Session = Depends(get_db),
                             current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_debugtalk.update_by = current_user.user.user_name
        edit_debugtalk.update_time = datetime.now()
        edit_debugtalk_result = DebugTalkService.edit_debugtalk_services(query_db, edit_debugtalk)
        if edit_debugtalk_result.is_success:
            logger.info(edit_debugtalk_result.message)
            return ResponseUtil.success(msg=edit_debugtalk_result.message)
        else:
            logger.warning(edit_debugtalk_result.message)
            return ResponseUtil.failure(msg=edit_debugtalk_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@debugtalkController.delete("/{debugtalk_ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:debugtalk:remove'))])
@log_decorator(title='DebugTalk管理', business_type=3)
async def delete_hrm_debugtalk(request: Request,
                               project_ids: str,
                               query_db: Session = Depends(get_db),
                               current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        delete_debugtalk = DeleteDebugTalkModel(projectIds=project_ids)
        delete_debugtalk.update_by = current_user.user.user_name
        delete_debugtalk.update_time = datetime.now()
        delete_debugtalk_result = DebugTalkService.delete_debugtalk_services(query_db, delete_debugtalk)
        if delete_debugtalk_result.is_success:
            logger.info(delete_debugtalk_result.message)
            return ResponseUtil.success(msg=delete_debugtalk_result.message)
        else:
            logger.warning(delete_debugtalk_result.message)
            return ResponseUtil.failure(msg=delete_debugtalk_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@debugtalkController.get("/{debugtalk_id}",
                         response_model=DebugTalkModel,
                         dependencies=[
                             Depends(CheckUserInterfaceAuth(['hrm:debugtalk:detail', "hrm:debugtalk:edit"], False))])
async def query_detail_system_debugtalk(request: Request, debugtalk_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_debugtalk_result = DebugTalkService.debugtalk_detail_services(query_db, debugtalk_id)
        logger.info(f'获取debugtalk_id为{debugtalk_id}的信息成功')
        return ResponseUtil.success(data=detail_debugtalk_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
