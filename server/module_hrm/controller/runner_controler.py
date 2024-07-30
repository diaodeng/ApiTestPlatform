from datetime import timezone, timedelta

from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.dao.env_dao import EnvDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.case_vo import *
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.enums.enums import CaseRunStatus
from module_hrm.service.case_service import *
from module_hrm.service.runner.case_data_handler import CaseInfoHandle
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.service.runner.runner_service import run_by_batch
from utils.log_util import *
from utils.page_util import *
from utils.response_util import *

runnerController = APIRouter(prefix='/hrm/runner', dependencies=[Depends(LoginService.get_current_user)])


@runnerController.post("/test", response_model=CaseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:test'))])
async def run_test(request: Request,
                   run_info: CaseRunModel,
                   query_db: Session = Depends(get_db),
                   current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                   ):
    try:
        # 获取分页数据
        run_result = run_by_batch(query_db, run_info.ids, run_info.env, run_info.run_type,
                                  user=current_user.user.user_id)
        logger.info('执行成功')
        data = ResponseUtil.success(data=run_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@runnerController.post("/debug", response_model=PageResponseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth(['hrm:api:debug', 'hrm:case:debug']))])
async def for_debug(request: Request, debug_info: CaseRunModel, query_db: Session = Depends(get_db)):
    try:
        # 获取分页数据
        case_data = debug_info.case_data
        case_id = case_data["caseId"]
        if isinstance(case_data, CaseModel):
            case_data = case_data.model_dump(by_alias=True)
        page_query_result = CaseModelForApi(**case_data)
        env_obj = EnvDao.get_env_by_id(query_db, debug_info.env)
        data_for_run = CaseInfoHandle(page_query_result).from_page().toDebug(EnvModel.from_orm(env_obj)).run_data()

        data_for_run.case_id = case_id

        test_runner = TestRunner(data_for_run)
        all_case_res = await test_runner.start()
        logger.info('执行成功')
        result_data = all_case_res[0]
        run_detail = RunDetailDao.create(query_db,
                                         result_data.result.case_id,
                                         None,
                                         debug_info.run_type,
                                         result_data.result.name,
                                         datetime.fromtimestamp(result_data.result.time.start_time).astimezone(timezone(timedelta(hours=8))),
                                         datetime.fromtimestamp(result_data.result.time.end_time).astimezone(timezone(timedelta(hours=8))),
                                         result_data.result.time.duration,
                                         result_data.result.model_dump_json(by_alias=True),
                                         1 if result_data.result.status == CaseRunStatus.passed.value else 2,
                                         )
        all_log = []
        for step_result in all_case_res:
            all_log.append("\n".join(step_result.result.log.values()))
        data = ResponseUtil.success(data={"log": "\n".join(all_log), "runId": run_detail.run_id})
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
