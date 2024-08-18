from fastapi import APIRouter, Request
from fastapi import Depends

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService
from module_hrm.dao.debugtalk_dao import DebugTalkDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.report_vo import ReportCreatModel, ReportQueryModel, ReportDelModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel
from module_hrm.service.case_service import *
from module_hrm.utils import comparators, debugtalk_common, util
from module_hrm.service.debugtalk_service import DebugTalkService, DebugTalkHandler
from utils.page_util import *
from utils.response_util import *

hrmCommonController = APIRouter(prefix='/hrm/common', dependencies=[Depends(LoginService.get_current_user)])


@hrmCommonController.get("/configDataType")
async def report_list(request: Request, query_info: ReportQueryModel = Depends(ReportQueryModel.as_query),
                      query_db: Session = Depends(get_db)):
    return ResponseUtil.success(data="未实现")


@hrmCommonController.get("/comparator")
async def report_detail(request: Request,
                        case_id: int | None = None,
                        project_id: int | None = None,
                        query_db: Session = Depends(get_db)):
    comparator_map = util.get_func_doc_map(comparators)

    common_debugtalk, project_debugtalk = DebugTalkService.debugtalk_source(query_db,
                                                                            project_id=project_id,
                                                                            case_id=case_id)
    debugtalk_handler = DebugTalkHandler(project_debugtalk, common_debugtalk)
    debugtalk_comparator_map = debugtalk_handler.func_doc_map(
        filter=lambda func: func.startswith("assert_"))
    comparator_map.update(debugtalk_comparator_map)
    debugtalk_handler.del_import()
    return ResponseUtil.success(data=comparator_map)


@hrmCommonController.get("/functions")
async def report_del(request: Request, case_id: int | None = None, query_db: Session = Depends(get_db)):
    common_debugtalk, project_debugtalk = DebugTalkService.debugtalk_source(query_db, case_id=case_id)
    debugtalk_handler = DebugTalkHandler(project_debugtalk, common_debugtalk)
    debugtalk_comparator_map = debugtalk_handler.func_doc_map(
        filter=lambda func: not func.startswith("assert_"))
    debugtalk_handler.del_import()
    return ResponseUtil.success(data=debugtalk_comparator_map)
