from fastapi import APIRouter, Request, HTTPException  # noqa: I001
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi import Depends
from sqlalchemy.orm import Session
from loguru import logger
import datetime
# import pdfkit

from config.get_db import get_db
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.service.login_service import LoginService
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_error_dao import RunErrorDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportDelModel, ReportQueryModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel
from module_hrm.entity.vo.run_error_vo import RunErrorQueryModel
from module_hrm.service.case_service import CurrentUserModel
from module_hrm.service.report_service import ReportService
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

reportController = APIRouter(prefix='/hrm/report', dependencies=[Depends(LoginService.get_current_user)])


@reportController.get("/list", response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:list']))])
async def report_list(request: Request,
                      query_info: ReportQueryModel = Depends(ReportQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      data_scope_sql: DataScopeExpr = Depends(GetDataScope(HrmReport, user_alias='manager'))

                      ):
    query_info.manager = current_user.user.user_id
    result = await ReportDao.get_list(query_db, query_info, data_scope_sql)
    return ResponseUtil.success(model_content=result)


@reportController.get("/{report_id}",
                      response_model=PageResponseModel,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:detail']))])
async def report_detail(request: Request,
                        report_id: int,
                        query_db: Session = Depends(get_db),
                        # data_scope_sql: DataScopeExpr = Depends(GetDataScope('HrmRunDetail', user_alias='manager')),
                        ):
    query_obj = RunDetailQueryModel(**{"report_id": report_id})

    result = await RunDetailDao.list(query_db, query_obj)
    return ResponseUtil.success(model_content=result)


@reportController.get(
    "/{report_id}/errorSummary",
    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:detail']))],
)
async def report_error_summary(
    request: Request,
    report_id: int,
    only_self: bool = False,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    summary = await RunErrorDao.get_summary_by_report(
        query_db,
        report_id,
        manager=current_user.user.user_id,
        only_self=only_self,
    )
    return ResponseUtil.success(model_content=summary)


@reportController.get(
    "/{report_id}/errorRecords",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:detail']))],
)
async def report_error_records(
    request: Request,
    report_id: int,
    query_info: RunErrorQueryModel = Depends(RunErrorQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    query_info.report_id = report_id
    # query_info.manager = current_user.user.user_id
    result = await RunErrorDao.list(query_db, query_info)
    return ResponseUtil.success(model_content=result)


@reportController.delete("",
                         response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:delete']))])
async def report_del(request: Request, query_info: ReportDelModel, query_db: Session = Depends(get_db)):
    result = await ReportService.delete_reports(query_db, query_info)
    if result.is_success:
        return ResponseUtil.success(
            dict_content={"msg": result.message, "deletedCount": result.result.get("deletedCount", 0)}
        )
    return ResponseUtil.failure(msg=result.message)


@reportController.get("/export/htmlold",
                      response_class=HTMLResponse,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:downloadHtml']))]
                      )
async def export_html_old(
    request: Request,
    query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    # data_scope_sql: DataScopeExpr = Depends(GetDataScope('HrmRunDetail', user_alias='manager'))
):
    try:
        # 1. 从数据库获取数据 (示例使用伪代码)
        # data = await db.fetch("SELECT * FROM items")
        query_info.manager = current_user.user.user_id
        query_info.is_page = False
        html_content = await ReportService.generate_html_report(query_db, query_info)
        file_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # 3. 设置下载头
        headers = {
            "Content-Disposition": f"attachment; filename=report_{file_time}.html"
        }
        return HTMLResponse(content=html_content, headers=headers)

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@reportController.get("/export/html",
                      response_class=HTMLResponse,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:downloadHtml']))]
                      )
async def export_html(request: Request,
                      query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      # data_scope_sql: DataScopeExpr = Depends(GetDataScope('HrmRunDetail', user_alias='manager'))
                      ):
    try:
        # 1. 从数据库获取数据 (示例使用伪代码)
        query_info.manager = current_user.user.user_id
        query_info.is_page = False
        file_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # 3. 设置下载头
        headers = {
            "Content-Disposition": f"attachment; filename=report_{file_time}.html"
        }
        return StreamingResponse(
            ReportService.generate_html_report(query_db, query_info),
            media_type="text/html",
            headers=headers
        )

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@reportController.get("/export/pdf",
                        dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:downloadPdf']))]
                      )
async def export_pdf(request: Request,
                      query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      # data_scope_sql: DataScopeExpr = Depends(GetDataScope('HrmRunDetail', user_alias='manager'))
                     ):
    query_info.manager = current_user.user.user_id
    query_info.is_page = False
    html_content = await ReportService.generate_pdf_report(query_db, query_info)
    return Response(content=html_content, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=report.pdf"})
