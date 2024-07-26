from fastapi import APIRouter, Request
from fastapi import Depends
from config.get_db import get_db
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.service.env_service import *
from utils.response_util import *
from utils.log_util import *
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.aspect.data_scope import GetDataScope
from module_admin.annotation.log_annotation import log_decorator
from utils.snowflake import snowIdWorker

envController = APIRouter(prefix='/hrm/env', dependencies=[Depends(LoginService.get_current_user)])


@envController.get("/list", response_model=List[EnvModel], dependencies=[Depends(CheckUserInterfaceAuth('hrm:env:list'))])
async def get_hrm_env_list(request: Request, env_query: EnvQueryModel = Depends(EnvQueryModel.as_query), query_db: Session = Depends(get_db), data_scope_sql: str = Depends(GetDataScope('HrmEnv'))):
    try:
        evn_query_result = EnvService.get_env_list_services(query_db, env_query, data_scope_sql)
        logger.info('获取成功')
        return ResponseUtil.success(data=evn_query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@envController.post("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:env:add'))])
@log_decorator(title='环境管理', business_type=1)
async def add_hrm_env(request: Request, add_env: EnvModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        add_env.create_by = current_user.user.user_name
        add_env.update_by = current_user.user.user_name
        add_env.env_id =snowIdWorker.get_id()
        add_env_result = EnvService.add_env_services(query_db, add_env)
        if add_env_result.is_success:
            logger.info(add_env_result.message)
            return ResponseUtil.success(data=add_env_result)
        else:
            logger.warning(add_env_result.message)
            return ResponseUtil.failure(msg=add_env_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@envController.put("", dependencies=[Depends(CheckUserInterfaceAuth('hrm:env:edit'))])
@log_decorator(title='环境管理', business_type=2)
async def edit_hrm_env(request: Request, edit_env: EnvModel, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        edit_env.update_by = current_user.user.user_name
        edit_env.update_time = datetime.now()
        edit_env_result = EnvService.edit_env_services(query_db, edit_env)
        if edit_env_result.is_success:
            logger.info(edit_env_result.message)
            return ResponseUtil.success(msg=edit_env_result.message)
        else:
            logger.warning(edit_env_result.message)
            return ResponseUtil.failure(msg=edit_env_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@envController.delete("/{env_ids}", dependencies=[Depends(CheckUserInterfaceAuth('hrm:env:remove'))])
@log_decorator(title='环境管理', business_type=3)
async def delete_hrm_env(request: Request, env_ids: str, query_db: Session = Depends(get_db), current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    try:
        print(env_ids)
        delete_env = DeleteEnvModel(envIds=env_ids)
        delete_env.update_by = current_user.user.user_name
        delete_env.update_time = datetime.now()
        delete_env_result = EnvService.delete_env_services(query_db, delete_env)
        if delete_env_result.is_success:
            logger.info(delete_env_result.message)
            return ResponseUtil.success(msg=delete_env_result.message)
        else:
            logger.warning(delete_env_result.message)
            return ResponseUtil.failure(msg=delete_env_result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@envController.get("/{env_id}", response_model=EnvModel, dependencies=[Depends(CheckUserInterfaceAuth(['hrm:env:detail', "hrm:env:edit"], False))])
async def query_detail_system_env(request: Request, env_id: int, query_db: Session = Depends(get_db)):
    try:
        detail_env_result = EnvService.env_detail_services(query_db, env_id)
        logger.info(f'获取env_id为{env_id}的信息成功')
        dict_content = detail_env_result.model_dump(exclude_unset=True, by_alias=True)
        return ResponseUtil.success(data=dict_content)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
