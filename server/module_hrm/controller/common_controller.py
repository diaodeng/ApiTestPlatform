import datetime
from loguru import logger

from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.service.login_service import LoginService
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.do.suite_do import QtrSuite
from module_hrm.entity.vo.report_vo import ReportQueryModel
from module_hrm.enums.enums import CaseRunStatus, DataType, RunTypeEnum
from module_hrm.service.case_service import Session, HrmCase
from module_hrm.service.common import get_base_counts_optimized, get_run_statistics, get_base_counts_subquery
from module_hrm.service.debugtalk_service import DebugTalkService, DebugTalkHandler
from module_hrm.utils import comparators, util
from utils.response_util import ResponseUtil

hrmCommonController = APIRouter(prefix='/hrm/common', dependencies=[Depends(LoginService.get_current_user)])


@hrmCommonController.get("/configDataType")
async def config_data_type(request: Request, query_info: ReportQueryModel = Depends(ReportQueryModel.as_query),
                           query_db: Session = Depends(get_db)):
    return ResponseUtil.success(data="未实现")


@hrmCommonController.get("/comparator")
async def comparators_dict(request: Request,
                           case_id: int | None = None,
                           project_id: int | None = None,
                           query_db: Session = Depends(get_db)):
    comparator_map = util.get_func_doc_map(comparators)

    common_debugtalk, project_debugtalk = await DebugTalkService.debugtalk_source(query_db,
                                                                            project_id=project_id,
                                                                            case_id=case_id)
    debugtalk_handler = DebugTalkHandler(project_debugtalk, common_debugtalk)
    debugtalk_comparator_map = debugtalk_handler.func_doc_map(
        filter=lambda func: func.startswith("assert_"))
    comparator_map.update(debugtalk_comparator_map)
    debugtalk_handler.del_import()
    return ResponseUtil.success(data=comparator_map)


@hrmCommonController.get("/functions")
async def functions_dict(request: Request, case_id: int | None = None, query_db: Session = Depends(get_db)):
    common_debugtalk, project_debugtalk = await DebugTalkService.debugtalk_source(query_db, case_id=case_id)
    debugtalk_handler = DebugTalkHandler(project_debugtalk, common_debugtalk)
    debugtalk_comparator_map = debugtalk_handler.func_doc_map(
        filter=lambda func: not func.startswith("assert_"))
    debugtalk_handler.del_import()
    return ResponseUtil.success(data=debugtalk_comparator_map)


@hrmCommonController.get("/countInfo")
async def count_info(request: Request, query_db: Session = Depends(get_db)):
    data = {}
    try:
        # 并行执行基础统计和运行统计

        base_counts = await get_base_counts_subquery(query_db)
        run_stats = await get_run_statistics(query_db)

        data =  {
            'projectCount': base_counts['project'],
            'moduleCount': base_counts['module'],
            'suiteCount': base_counts['suite'],
            'caseCount': base_counts['case'],
            'total': run_stats
        }
    except Exception as e:
        logger.error(f"统计信息查询失败: {e}")
        # 返回默认值或缓存数据
        # return get_default_count_info()

    return ResponseUtil.success(data=data)
