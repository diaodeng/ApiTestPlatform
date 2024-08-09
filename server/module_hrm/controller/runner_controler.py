import time
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService, CurrentUserModel
from module_hrm.dao.env_dao import EnvDao
from module_hrm.dao.report_dao import ReportDao
from module_hrm.entity.vo.report_vo import ReportCreatModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, RunDetailDelModel, HrmRunDetailModel
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.case_vo import *
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.enums.enums import CaseRunStatus
from module_hrm.service.case_service import *
from module_hrm.service.runner.case_data_handler import CaseInfoHandle
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.service.runner.runner_service import run_by_batch
from module_hrm.service.debugtalk_service import DebugTalkService, DebugTalkHandler
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
        for i in range(run_info.repeat_num):
            test_start_time = time.time()
            run_result = await run_by_batch(query_db, run_info.ids, run_info.env, run_info.run_type, run_info.run_model,
                                            user=current_user.user.user_id)
            test_end_time = time.time()
            logger.info('执行成功')
            report_name = run_info.report_name or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if run_info.repeat_num > 1:
                report_name = f"{report_name}-{i + 1}"

            report_data = ReportCreatModel(**{"reportName": report_name,
                                              "status": CaseRunStatus.passed.value,
                                              })
            report_info = ReportDao.create(query_db, report_data)
            report_info.start_at = datetime.fromtimestamp(test_start_time, timezone.utc).astimezone(
                timezone(timedelta(hours=8)))
            report_info.test_duration = test_end_time - test_start_time
            report_status = report_info.status
            report_total = 0
            report_success = 0
            for step_result in run_result:
                run_detail = RunDetailDao.create(query_db,
                                                 step_result.case_id,
                                                 report_info.report_id,
                                                 RunType.case.value,
                                                 step_result.name,
                                                 datetime.fromtimestamp(step_result.time.start_time,
                                                                        timezone.utc).astimezone(
                                                     timezone(timedelta(hours=8))),
                                                 datetime.fromtimestamp(step_result.time.end_time,
                                                                        timezone.utc).astimezone(
                                                     timezone(timedelta(hours=8))),
                                                 step_result.time.duration,
                                                 step_result.model_dump_json(by_alias=True),
                                                 step_result.status,
                                                 )
                report_total += 1
                if step_result.status == CaseRunStatus.failed.value:
                    report_status = CaseRunStatus.failed.value
                elif step_result.status == CaseRunStatus.passed.value:
                    report_success += 1

            report_info.status = report_status
            report_info.total = report_total
            report_info.success = report_success
            query_db.commit()

        data = ResponseUtil.success(data=f"执行成功，执行了{run_info.repeat_num}次，请前往报告查看")
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@runnerController.post("/debug", response_model=PageResponseModel,
                       dependencies=[Depends(CheckUserInterfaceAuth(['hrm:api:debug', 'hrm:case:debug']))])
async def for_debug(request: Request, debug_info: CaseRunModel, query_db: Session = Depends(get_db),
                    current_user: CurrentUserModel = Depends(LoginService.get_current_user)):
    debugtalk_obj = None
    try:
        case_data = debug_info.case_data
        page_query_result = CaseModelForApi(**case_data)
        data_for_run = CaseInfoHandle(query_db).from_page(case_data).toDebug(debug_info.env).run_data()

        # 读取项目debugtalk
        common_debugtalk_source, project_debugtalk_source = DebugTalkService.debugtalk_source_for_projectid(query_db,
                                                                                                            project_id=page_query_result.project_id)
        debugtalk_obj = DebugTalkHandler(project_debugtalk_source, common_debugtalk_source)
        debugtalk_func_map = debugtalk_obj.func_map(user=current_user.user.user_id)
        data_for_run.case_id = page_query_result.case_id

        test_runner = TestRunner(data_for_run, debugtalk_func_map)
        all_case_res = await test_runner.start()
        logger.info('执行成功')
        all_log = []
        for step_result in all_case_res:
            case_run_data = step_result.case_data
            RunDetailDao.create(query_db,
                                page_query_result.case_id,
                                None,
                                debug_info.run_type,
                                step_result.result.name,
                                datetime.fromtimestamp(step_result.result.time.start_time,
                                                       timezone.utc).astimezone(
                                    timezone(timedelta(hours=8))),
                                datetime.fromtimestamp(step_result.result.time.end_time,
                                                       timezone.utc).astimezone(
                                    timezone(timedelta(hours=8))),
                                step_result.result.time.duration,
                                step_result.result.model_dump_json(by_alias=True),
                                step_result.result.status,
                                )

            all_log.append("\n".join(step_result.result.log.values()))
        data = ResponseUtil.success(data={"log": "\n".join(all_log), "runId": page_query_result.case_id})
        return data
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
    finally:
        if debugtalk_obj:
            debugtalk_obj.del_import()


@runnerController.get("/runHistory/{detail_id}", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:history:detail']))])
async def run_history_detail(request: Request, detail_id: int, query_db: Session = Depends(get_db)):
    result = RunDetailDao.get_by_id(query_db, detail_id)
    return ResponseUtil.success(
        data=HrmRunDetailModel(**CamelCaseUtil.transform_result(result)).model_dump(by_alias=True))


@runnerController.get("/runHistoryList", response_model=PageResponseModel,
                      dependencies=[
                          Depends(CheckUserInterfaceAuth(['hrm:history:list', 'hrm:case:history', 'hrm:api:history']))])
async def run_history_list(request: Request, query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                           query_db: Session = Depends(get_db)):
    result = RunDetailDao.list(query_db, query_info)
    return ResponseUtil.success(model_content=result)


@runnerController.delete("/runHistory", response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth(['hrm:history:delete']))])
async def run_history_del(request: Request, query_info: RunDetailDelModel, query_db: Session = Depends(get_db)):
    result = RunDetailDao.delete(query_db, query_info.detail_ids)
    return ResponseUtil.success(dict_content={"msg": "删除成功"})
