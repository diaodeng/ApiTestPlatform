import datetime

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
    project_count = query_db.query(HrmProject).count()
    module_count = query_db.query(HrmModule).count()
    suite_count = query_db.query(QtrSuite).count()
    case_count = query_db.query(HrmCase).filter(HrmCase.type == DataType.case.value).count()

    def get_total_values():
        total = {
            'pass': [],
            'fail': [],
            'percent': []
        }
        today = datetime.date.today()
        for i in range(-11, 1):
            begin = today + datetime.timedelta(days=i)
            end = begin + datetime.timedelta(days=1)

            total_run = query_db.query(HrmRunDetail).filter(HrmRunDetail.create_time.between(begin, end),
                                                            HrmRunDetail.run_type.in_([RunTypeEnum.case.value,
                                                                                       RunTypeEnum.model.value,
                                                                                       RunTypeEnum.suite.value,
                                                                                       RunTypeEnum.project.value,
                                                                                       ])).count()
            total_success = query_db.query(HrmRunDetail).filter(HrmRunDetail.create_time.between(begin, end),
                                                                HrmRunDetail.status == CaseRunStatus.passed.value,
                                                                HrmRunDetail.run_type.in_([RunTypeEnum.case.value,
                                                                                           RunTypeEnum.model.value,
                                                                                           RunTypeEnum.suite.value,
                                                                                           RunTypeEnum.project.value,
                                                                                           ])).count()

            if not total_run:
                total_run = 0
            if not total_success:
                total_success = 0

            total_percent = round(total_success / total_run * 100, 2) if total_run != 0 else 0.00
            total['pass'].append(total_success)
            total['fail'].append(total_run - total_success)
            total['percent'].append(total_percent)

        return total

    total = get_total_values()

    data = {
        'projectCount': project_count,
        'moduleCount': module_count,
        'caseCount': case_count,
        'suiteCount': suite_count,
        # 'account': request.session.get("now_account", 'test'),
        'total': total
    }
    return ResponseUtil.success(data=data)
