from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.entity.do.web_case_do import HrmWebCase
from module_hrm.entity.vo.web_case_vo import (
    AddWebCaseModel,
    WebCaseDetailModel,
    WebCasePageQueryModel,
    WebCaseRunRecordPageQueryModel,
    WebCaseRunRequestModel,
    WebRecordingApplyRequestModel,
    WebRecordingReplayRequestModel,
    WebRecordingSaveCaseRequestModel,
    WebRecordingSessionPageQueryModel,
    WebRecordingStartRequestModel,
    WebRecordingStopRequestModel,
)
from module_hrm.service.web_case_service import WebCaseService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

webCaseController = APIRouter(
    prefix="/hrm/web-case",
    dependencies=[Depends(LoginService.get_current_user)],
)


@webCaseController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:list"))],
)
async def get_web_case_list(
    request: Request,
    page_query: WebCasePageQueryModel = Depends(WebCasePageQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    data_scope_sql: DataScopeExpr = Depends(GetDataScope(HrmWebCase, user_alias="manager")),
):
    try:
        page_query.manager = current_user.user.user_id
        page_result = WebCaseService.get_web_case_list_services(query_db, page_query, data_scope_sql)
        return ResponseUtil.success(model_content=page_result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.get(
    "/{web_case_id}",
    response_model=WebCaseDetailModel,
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:webCase:detail", "hrm:webCase:edit"], False))],
)
async def get_web_case_detail(
    request: Request,
    web_case_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = WebCaseService.web_case_detail_services(query_db, web_case_id)
        if detail is None:
            return ResponseUtil.failure(msg="Web用例不存在")
        return ResponseUtil.success(data=detail.model_dump(by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post("", dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:add"))])
@log_decorator(title="Web用例管理", business_type=1)
async def add_web_case(
    request: Request,
    add_case: AddWebCaseModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        add_case.manager = current_user.user.user_id
        add_case.dept_id = current_user.user.dept_id
        add_case.create_by = current_user.user.user_name
        add_case.update_by = current_user.user.user_name
        result = WebCaseService.add_web_case_services(query_db, add_case)
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.put("", dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:edit"))])
@log_decorator(title="Web用例管理", business_type=2)
async def edit_web_case(
    request: Request,
    edit_case: WebCaseDetailModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        edit_case.manager = current_user.user.user_id
        edit_case.dept_id = current_user.user.dept_id
        edit_case.update_by = current_user.user.user_name
        edit_case.update_time = datetime.now()
        result = WebCaseService.edit_web_case_services(query_db, edit_case)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.delete(
    "/{web_case_ids}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:remove"))],
)
@log_decorator(title="Web用例管理", business_type=3)
async def delete_web_case(
    request: Request,
    web_case_ids: str,
    query_db: Session = Depends(get_db),
):
    try:
        result = WebCaseService.delete_web_case_services(query_db, web_case_ids)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/run",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:run"))],
)
@log_decorator(title="Web用例执行", business_type=0)
async def run_web_case(
    request: Request,
    run_request: WebCaseRunRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = await WebCaseService.run_web_case_services(
            query_db,
            run_request,
            manager=current_user.user.user_id,
            dept_id=current_user.user.dept_id,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.get(
    "/run/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:history"))],
)
async def list_run_record(
    request: Request,
    page_query: WebCaseRunRecordPageQueryModel = Depends(WebCaseRunRecordPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    try:
        result = WebCaseService.list_run_record_services(query_db, page_query)
        return ResponseUtil.success(model_content=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.get(
    "/run/{web_case_run_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:history"))],
)
async def get_run_record_detail(
    request: Request,
    web_case_run_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = WebCaseService.run_record_detail_services(query_db, web_case_run_id)
        if detail is None:
            return ResponseUtil.failure(msg="执行记录不存在")
        return ResponseUtil.success(data=detail.model_dump(mode="json", by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/recording/start",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:record"))],
)
@log_decorator(title="Web录制启动", business_type=0)
async def start_recording(
    request: Request,
    start_request: WebRecordingStartRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = await WebCaseService.start_recording_services(
            query_db,
            start_request,
            manager=current_user.user.user_id,
            dept_id=current_user.user.dept_id,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/recording/stop",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:record"))],
)
@log_decorator(title="Web录制停止", business_type=0)
async def stop_recording(
    request: Request,
    stop_request: WebRecordingStopRequestModel,
    query_db: Session = Depends(get_db),
):
    try:
        result = await WebCaseService.stop_recording_services(query_db, stop_request)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.get(
    "/recording/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:record"))],
)
async def list_recording(
    request: Request,
    page_query: WebRecordingSessionPageQueryModel = Depends(WebRecordingSessionPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    try:
        result = WebCaseService.list_recording_services(query_db, page_query)
        return ResponseUtil.success(model_content=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.get(
    "/recording/{recording_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:record"))],
)
async def get_recording_detail(
    request: Request,
    recording_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = WebCaseService.recording_detail_services(query_db, recording_id)
        if detail is None:
            return ResponseUtil.failure(msg="录制会话不存在")
        return ResponseUtil.success(data=detail.model_dump(by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/recording/replay",
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:webCase:run", "hrm:webCase:record"], False))],
)
@log_decorator(title="录制回放", business_type=0)
async def replay_recording(
    request: Request,
    replay_request: WebRecordingReplayRequestModel,
    query_db: Session = Depends(get_db),
):
    try:
        result = await WebCaseService.replay_recording_services(query_db, replay_request)
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/recording/apply",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:edit"))],
)
@log_decorator(title="录制应用到Web用例", business_type=2)
async def apply_recording(
    request: Request,
    apply_request: WebRecordingApplyRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = WebCaseService.apply_recording_to_case_services(
            query_db,
            apply_request,
            manager=current_user.user.user_id,
            dept_id=current_user.user.dept_id,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@webCaseController.post(
    "/recording/save-as-case",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:webCase:add"))],
)
@log_decorator(title="录制保存为Web用例", business_type=1)
async def save_recording_as_case(
    request: Request,
    save_request: WebRecordingSaveCaseRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = WebCaseService.save_recording_as_case_services(
            query_db,
            save_request,
            manager=current_user.user.user_id,
            dept_id=current_user.user.dept_id,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))
