from fastapi import APIRouter, Request
from fastapi import Depends
from config.get_db import get_db
from config.get_loger import get_case_log, TestLog
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.service.case_service import *
from module_hrm.entity.vo.case_vo import *
from utils.response_util import *
from utils.log_util import *
from utils.page_util import *
from module_hrm.service.runner.runner_service import run_by_batch
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.service.runner.case_data_handler import CaseInfoHandle
from module_hrm.dao.env_dao import EnvDao
from module_hrm.entity.vo.env_vo import EnvModel
from utils.common_util import bytes2file_response
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.annotation.log_annotation import log_decorator
from utils.snowflake import snowIdWorker

caseController = APIRouter(prefix='/hrm/runner', dependencies=[Depends(LoginService.get_current_user)])


@caseController.post("/test", response_model=CaseModel, dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:test'))])
async def run_test(request: Request,
                   run_info: CaseRunModel,
                   query_db: Session = Depends(get_db),
                   current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                   ):
    try:
        # 获取分页数据
        run_result = run_by_batch(query_db, run_info.ids, run_info.env, run_info.run_type, user=current_user.user.user_id)
        logger.info('执行成功')
        data = ResponseUtil.success(data=run_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@caseController.post("/debug", response_model=PageResponseModel, dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:debug'))])
async def for_debug(request: Request, debug_info: CaseRunModel, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        page_query_result = CaseModelForApi(**debug_info.case_data.model_dump())
        env_obj = EnvDao.get_env_by_id(query_db, debug_info.env)
        data_for_run = CaseInfoHandle().from_page(page_query_result).toDebug(EnvModel(**env_obj)).run_data()
        TestRunner(data_for_run).start()
        logger.info('获取成功')
        data = ResponseUtil.success(model_content=page_query_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))