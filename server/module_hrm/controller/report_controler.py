from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.report_vo import ReportQueryModel, ReportDelModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel
from module_hrm.service.case_service import CurrentUserModel
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

reportController = APIRouter(prefix='/hrm/report', dependencies=[Depends(LoginService.get_current_user)])


@reportController.get("/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:list']))])
async def report_list(request: Request,
                      query_info: ReportQueryModel = Depends(ReportQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      data_scope_sql: str = Depends(GetDataScope('HrmReport', user_alias='manager'))

                      ):
    query_info.manager = current_user.user.user_id
    result = ReportDao.get_list(query_db, query_info, data_scope_sql)
    return ResponseUtil.success(model_content=result)


@reportController.get("/{report_id}",
                      response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:detail']))])
async def report_detail(request: Request,
                        report_id: int,
                        query_db: Session = Depends(get_db),
                        data_scope_sql: str = Depends(GetDataScope('HrmRunDetail', user_alias='manager')),
                        ):
    query_obj = RunDetailQueryModel(**{"report_id": report_id})

    result = RunDetailDao.list(query_db, query_obj, data_scope_sql)
    return ResponseUtil.success(model_content=result)


@reportController.delete("",
                         response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:delete']))])
async def report_del(request: Request, query_info: ReportDelModel, query_db: Session = Depends(get_db)):
    result = ReportDao.delete(query_db, query_info.report_ids)
    return ResponseUtil.success(dict_content={"msg": "删除成功"})
