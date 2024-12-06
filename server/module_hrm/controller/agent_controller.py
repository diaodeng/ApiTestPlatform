from datetime import datetime

from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.entity.vo.agent_vo import AgentModel, AgentQueryModel, DeleteAgentModel
from module_hrm.entity.vo.debugtalk_vo import DebugTalkModel
from module_hrm.service.agent_service import AgentService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil
from utils.snowflake import snowIdWorker

agentController = APIRouter(prefix='/qtr/agent', dependencies=[Depends(LoginService.get_current_user)])


@agentController.get("/list", response_model=list[AgentModel] | PageResponseModel,
                     dependencies=[Depends(CheckUserInterfaceAuth('qtr:agent:list'))])
async def get_qtr_agent_list(request: Request,
                             query: AgentQueryModel = Depends(AgentQueryModel.as_query),
                             query_db: Session = Depends(get_db),
                             data_scope_sql: str = Depends(GetDataScope('QtrAgent'))):
    try:
        query_result = AgentService.get_agent_list_services(query_db, query, data_scope_sql)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        else:
            return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@agentController.post("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:agent:add'))])
@log_decorator(title='Agent管理', business_type=1)
async def add_qtr_agent(request: Request,
                        add_agent: AgentModel,
                        query_db: Session = Depends(get_db),
                        current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_agent.manager = current_user.user.user_id
        add_agent.create_by = current_user.user.user_name
        add_agent.update_by = current_user.user.user_name
        add_agent.agent_id = snowIdWorker.get_id()
        add_agent_result = AgentService.add_agent_services(query_db, add_agent)
        if add_agent_result.is_success:
            logger.info(add_agent_result.message)
            return ResponseUtil.success(data=add_agent_result)
        else:
            logger.warning(add_agent_result.message)
            return ResponseUtil.failure(msg=add_agent_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@agentController.put("", dependencies=[Depends(CheckUserInterfaceAuth('qtr:agent:edit'))])
@log_decorator(title='Agent管理', business_type=2)
async def edit_qtr_agent(request: Request,
                         edit_agent: AgentModel,
                         query_db: Session = Depends(get_db),
                         current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_agent.update_by = current_user.user.user_name
        edit_agent.update_time = datetime.now()
        edit_agent_result = AgentService.edit_agent_services(query_db, edit_agent)
        if edit_agent_result.is_success:
            logger.info(edit_agent_result.message)
            return ResponseUtil.success(msg=edit_agent_result.message)
        else:
            logger.warning(edit_agent_result.message)
            return ResponseUtil.failure(msg=edit_agent_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@agentController.delete("/{agent_ids}", dependencies=[Depends(CheckUserInterfaceAuth('qtr:agent:remove'))])
@log_decorator(title='Agent管理', business_type=3)
async def delete_qtr_agent(request: Request,
                           agent_ids: str,
                           query_db: Session = Depends(get_db),
                           current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        delete_agent = DeleteAgentModel(projectIds=agent_ids)
        delete_agent.update_by = current_user.user.user_name
        delete_agent.update_time = datetime.now()
        delete_agent_result = AgentService.delete_agent_services(query_db, delete_agent)
        if delete_agent_result.is_success:
            logger.info(delete_agent_result.message)
            return ResponseUtil.success(msg=delete_agent_result.message)
        else:
            logger.warning(delete_agent_result.message)
            return ResponseUtil.failure(msg=delete_agent_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@agentController.get("/{agent_id}",
                     response_model=DebugTalkModel,
                     dependencies=[
                         Depends(CheckUserInterfaceAuth(['qtr:agent:detail', "qtr:agent:edit"], False))])
async def query_detail_system_debugtalk(request: Request, agent_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_agent_result = AgentService.agent_detail_services(query_db, agent_id)
        logger.info(f'获取agent_id为{agent_id}的信息成功')
        return ResponseUtil.success(data=detail_agent_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
