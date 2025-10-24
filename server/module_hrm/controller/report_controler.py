from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi import Depends
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
import datetime
import pdfkit


from config.get_db import get_db
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.service.login_service import LoginService
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.vo.report_vo import ReportQueryModel, ReportDelModel
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel
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
                      data_scope_sql: str = Depends(GetDataScope('HrmReport', user_alias='manager'))

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
                        # data_scope_sql: str = Depends(GetDataScope('HrmRunDetail', user_alias='manager')),
                        ):
    query_obj = RunDetailQueryModel(**{"report_id": report_id})

    result = await RunDetailDao.list(query_db, query_obj)
    return ResponseUtil.success(model_content=result)


@reportController.delete("",
                         response_model=PageResponseModel,
                         dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:delete']))])
async def report_del(request: Request, query_info: ReportDelModel, query_db: Session = Depends(get_db)):
    await ReportDao.delete(query_db, query_info.report_ids)
    return ResponseUtil.success(dict_content={"msg": "删除成功"})


@reportController.get("/export/html",
                      response_class=HTMLResponse,
                      dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:downloadHtml']))]
                      )
async def export_html(request: Request,
                      query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      # data_scope_sql: str = Depends(GetDataScope('HrmRunDetail', user_alias='manager'))
                      ):
    try:
        # 1. 从数据库获取数据 (示例使用伪代码)
        # data = await db.fetch("SELECT * FROM items")
        query_info.manager = current_user.user.user_id
        query_info.is_page = False
        html_content = await ReportService.generate_html_report(query_db, query_info)

        # 3. 设置下载头
        headers = {
            "Content-Disposition": "attachment; filename=report.html"
        }
        return HTMLResponse(content=html_content, headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@reportController.get("/export/pdf",
                        dependencies=[Depends(CheckUserInterfaceAuth(['hrm:report:downloadPdf']))]
                      )
async def export_pdf(request: Request,
                      query_info: RunDetailQueryModel = Depends(RunDetailQueryModel.as_query),
                      query_db: Session = Depends(get_db),
                      current_user: CurrentUserModel = Depends(LoginService.get_current_user),
                      # data_scope_sql: str = Depends(GetDataScope('HrmRunDetail', user_alias='manager'))
                     ):
    query_info.manager = current_user.user.user_id
    query_info.is_page = False
    html_content = await ReportService.generate_pdf_report(query_db, query_info)
    return Response(content=html_content, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=report.pdf"})