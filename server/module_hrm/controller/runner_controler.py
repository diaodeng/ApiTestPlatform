import asyncio

from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, RunDetailDelModel, HrmRunDetailModel
from module_hrm.service.case_service import *
from module_hrm.service.debugtalk_service import DebugTalkService, DebugTalkHandler
from module_hrm.service.runner.case_data_handler import CaseInfoHandle, ParametersHandler
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.service.runner.runner_service import run_by_async, save_run_detail
from utils.log_util import *
from utils.message_util import FeiShuHandler, MessageHandler
from utils.page_util import *
from utils.response_util import *

runnerController = APIRouter(prefix='/hrm/runner', dependencies=[Depends(LoginService.get_current_user)])


@runnerController.post("/test",
                       response_model=CaseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth('hrm:case:run'))])
async def run_test(request: Request,
                   run_info: CaseRunModel,
                   current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                   ):
    try:
        run_info.runner = current_user.user.user_id
        run_info.feishu_robot.push = run_info.push
        if run_info.is_async:
            asyncio.create_task(run_by_async(run_info, current_user))
            data = "请耐心等待运行结果"
        else:
            data = await run_by_async(run_info, current_user)

        return ResponseUtil.success(data=data, msg=data)
    except Exception as e:
        logger.exception(e)
        message_handler = MessageHandler(run_info)
        if message_handler.can_push():
            message_handler.feishu().push(f"[{current_user.user.user_name}]于{datetime.now()}开始的测试异常了")
        return ResponseUtil.error(msg=str(e))


@runnerController.post("/debug",
                       response_model=PageResponseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth(['hrm:api:debug', 'hrm:case:debug']))])
async def for_debug(request: Request,
                    debug_info: CaseRunModel,
                    query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    debugtalk_obj = None
    try:
        debug_info.runner = current_user.user.user_id
        case_data = debug_info.case_data
        if not isinstance(case_data, dict):
            case_data = case_data.model_dump(by_alias=True)
        page_query_result = CaseModelForApi(**case_data)
        data_for_run = CaseInfoHandle(query_db).from_page(page_query_result).toDebug(debug_info.env).run_data()
        case_objs = ParametersHandler.get_parameters_case([data_for_run])

        if not case_objs: return ResponseUtil.success(msg="没有可执行的用例", data="没有可执行的用例")

        # 读取项目debugtalk
        common_debugtalk_source, project_debugtalk_source = DebugTalkService.debugtalk_source(query_db,
                                                                                              project_id=page_query_result.project_id)
        debugtalk_obj = DebugTalkHandler(project_debugtalk_source, common_debugtalk_source)
        debugtalk_func_map = debugtalk_obj.func_map(user=current_user.user.user_id)

        test_runner = TestRunner(case_objs[0], debugtalk_func_map, debug_info)
        all_case_res = await test_runner.start()
        logger.info('执行成功')
        all_log = []
        steps_result = {}
        for case_result in all_case_res:
            case_run_data = case_result
            await save_run_detail(query_db, case_run_data, run_info=debug_info)

            for step in case_run_data.teststeps:
                steps_result[step.step_id] = step.result.model_dump(by_alias=True)
                all_log.append(step.result.logs)

            # all_log.append("\n".join(step_result.result.log.values()))
        data = ResponseUtil.success(data=steps_result)
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
    finally:
        if debugtalk_obj:
            debugtalk_obj.del_import()


@runnerController.get("/runHistory/{detail_id}",
                      response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:history:detail']))])
async def run_history_detail(request: Request,
                             detail_id: int,
                             query_db: Session = Depends(get_db)):
    result = RunDetailDao.get_by_id(query_db, detail_id)
    run_detail = CaseInfoHandle(query_db).from_db_run_detail(result.run_detail).toPage().asCase().model_dump(
        by_alias=True)
    return ResponseUtil.success(
        data=run_detail)


@runnerController.get("/runHistoryList",
                      response_model=PageResponseModel,
                      dependencies=[
                          Depends(CheckUserInterfaceAuth(['hrm:history:list', 'hrm:case:history', 'hrm:api:history']))])
async def run_history_list(request: Request,
                           query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                           query_db: Session = Depends(get_db),
                           current_user: CurrentUserModel = Depends(LoginService.get_current_user)
                           ):
    query_info.manager = current_user.user.user_id
    result = RunDetailDao.list(query_db, query_info)
    return ResponseUtil.success(model_content=result)


@runnerController.delete("/runHistory",
                         response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth(['hrm:history:delete']))])
async def run_history_del(request: Request,
                          query_info: RunDetailDelModel,
                          query_db: Session = Depends(get_db)):
    result = RunDetailDao.delete(query_db, query_info.detail_ids)
    return ResponseUtil.success(dict_content={"msg": "删除成功"})
