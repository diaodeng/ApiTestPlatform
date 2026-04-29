import mimetypes
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.data_scope import GetDataScope
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.common_vo import DataScopeExpr
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from module_hrm.entity.do.desktop_case_do import HrmDesktopCase
from module_hrm.entity.vo.desktop_case_vo import (
    AddDesktopCaseModel,
    DesktopCaseDetailModel,
    DesktopImageStorageConfigModel,
    DesktopCasePageQueryModel,
    DesktopCaseRunRecordPageQueryModel,
    DesktopCaseRunRequestModel,
    DesktopRecordingApplyRequestModel,
    DesktopRecordingEventUpdateRequestModel,
    DesktopRecordingReplayRequestModel,
    DesktopRecordingSaveCaseRequestModel,
    DesktopRecordingSessionPageQueryModel,
    DesktopRecordingStartRequestModel,
    DesktopRecordingStopRequestModel,
    DesktopReplaceBaselineRequestModel,
)
from module_hrm.service.desktop_case_service import DesktopCaseService
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil

desktopCaseAssetController = APIRouter()


@desktopCaseAssetController.get("/hrm/desktop-case/assets/{asset_id}")
async def get_desktop_asset_content(
    asset_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        result = DesktopCaseService.read_asset_bytes_services(query_db, asset_id)
        if result is None:
            raise HTTPException(status_code=404, detail="桌面截图不存在")
        asset, asset_bytes = result
        media_type, _encoding = mimetypes.guess_type(str(asset.file_name or asset.file_path or ""))
        return Response(
            content=asset_bytes,
            media_type=media_type or "application/octet-stream",
            headers={"Cache-Control": "public, max-age=300"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@desktopCaseAssetController.get("/desktop-test/{asset_path:path}")
async def get_desktop_asset_by_path(
    asset_path: str,
    query_db: Session = Depends(get_db),
):
    try:
        normalized_path = f"{DesktopCaseService.IMAGE_DIR_NAME}/{asset_path or ''}".rstrip("/")
        asset_bytes = DesktopCaseService.read_asset_bytes_by_path_services(
            query_db,
            normalized_path,
        )
        if asset_bytes is None:
            raise HTTPException(status_code=404, detail="桌面截图不存在")
        media_type, _encoding = mimetypes.guess_type(str(asset_path or ""))
        return Response(
            content=asset_bytes,
            media_type=media_type or "application/octet-stream",
            headers={"Cache-Control": "public, max-age=300"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


desktopCaseController = APIRouter(
    prefix="/hrm/desktop-case",
    dependencies=[Depends(LoginService.get_current_user)],
)


@desktopCaseController.get(
    "/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:list"))],
)
async def get_desktop_case_list(
    request: Request,
    page_query: DesktopCasePageQueryModel = Depends(DesktopCasePageQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
    data_scope_sql: DataScopeExpr = Depends(GetDataScope(HrmDesktopCase, user_alias="manager")),
):
    try:
        page_result = DesktopCaseService.get_desktop_case_list_services(query_db, page_query, data_scope_sql)
        return ResponseUtil.success(model_content=page_result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.get(
    "/{desktop_case_id}",
    response_model=DesktopCaseDetailModel,
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:desktopCase:detail", "hrm:desktopCase:edit"], False))],
)
async def get_desktop_case_detail(
    request: Request,
    desktop_case_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = DesktopCaseService.desktop_case_detail_services(query_db, desktop_case_id)
        if detail is None:
            return ResponseUtil.failure(msg="桌面用例不存在")
        return ResponseUtil.success(data=detail.model_dump(mode="json", by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.get(
    "/storage-config",
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:desktopCase:detail", "hrm:desktopCase:edit"], False))],
)
async def get_desktop_image_storage_config(
    request: Request,
    query_db: Session = Depends(get_db),
):
    try:
        detail = DesktopCaseService.get_image_storage_config_services(query_db)
        return ResponseUtil.success(data=detail.model_dump(mode="json", by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/storage-config",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:edit"))],
)
@log_decorator(title="桌面截图存储配置", business_type=2)
async def save_desktop_image_storage_config(
    request: Request,
    storage_config: DesktopImageStorageConfigModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = DesktopCaseService.save_image_storage_config_services(
            query_db,
            storage_config,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post("", dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:add"))])
@log_decorator(title="桌面用例管理", business_type=1)
async def add_desktop_case(
    request: Request,
    add_case: AddDesktopCaseModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        add_case.manager = current_user.user.user_id
        add_case.dept_id = current_user.user.dept_id
        add_case.create_by = current_user.user.user_name
        add_case.update_by = current_user.user.user_name
        result = DesktopCaseService.add_desktop_case_services(query_db, add_case)
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.put("", dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:edit"))])
@log_decorator(title="桌面用例管理", business_type=2)
async def edit_desktop_case(
    request: Request,
    edit_case: DesktopCaseDetailModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        edit_case.manager = current_user.user.user_id
        edit_case.dept_id = current_user.user.dept_id
        edit_case.update_by = current_user.user.user_name
        edit_case.update_time = datetime.now()
        result = DesktopCaseService.edit_desktop_case_services(query_db, edit_case)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.delete(
    "/{desktop_case_ids}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:remove"))],
)
@log_decorator(title="桌面用例管理", business_type=3)
async def delete_desktop_case(
    request: Request,
    desktop_case_ids: str,
    query_db: Session = Depends(get_db),
):
    try:
        result = DesktopCaseService.delete_desktop_case_services(query_db, desktop_case_ids)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/run",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:run"))],
)
@log_decorator(title="桌面用例执行", business_type=0)
async def run_desktop_case(
    request: Request,
    run_request: DesktopCaseRunRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = await DesktopCaseService.run_desktop_case_services(
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


@desktopCaseController.get(
    "/run/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:history"))],
)
async def list_run_record(
    request: Request,
    page_query: DesktopCaseRunRecordPageQueryModel = Depends(DesktopCaseRunRecordPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    try:
        result = DesktopCaseService.list_run_record_services(query_db, page_query)
        return ResponseUtil.success(model_content=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.get(
    "/run/{desktop_case_run_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:history"))],
)
async def get_run_record_detail(
    request: Request,
    desktop_case_run_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = DesktopCaseService.run_record_detail_services(query_db, desktop_case_run_id)
        if detail is None:
            return ResponseUtil.failure(msg="执行记录不存在")
        return ResponseUtil.success(data=detail.model_dump(mode="json", by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/run/replace-baseline",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:edit"))],
)
@log_decorator(title="桌面基准替换", business_type=2)
async def replace_baseline(
    request: Request,
    replace_request: DesktopReplaceBaselineRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = DesktopCaseService.replace_baseline_services(
            query_db,
            replace_request,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/recording/start",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:record"))],
)
@log_decorator(title="桌面录制启动", business_type=0)
async def start_recording(
    request: Request,
    start_request: DesktopRecordingStartRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = await DesktopCaseService.start_recording_services(
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


@desktopCaseController.post(
    "/recording/stop",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:record"))],
)
@log_decorator(title="桌面录制停止", business_type=0)
async def stop_recording(
    request: Request,
    stop_request: DesktopRecordingStopRequestModel,
    query_db: Session = Depends(get_db),
):
    try:
        result = await DesktopCaseService.stop_recording_services(query_db, stop_request)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.get(
    "/recording/list",
    response_model=PageResponseModel,
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:record"))],
)
async def list_recording(
    request: Request,
    page_query: DesktopRecordingSessionPageQueryModel = Depends(DesktopRecordingSessionPageQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    try:
        result = DesktopCaseService.list_recording_services(query_db, page_query)
        return ResponseUtil.success(model_content=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.get(
    "/recording/{recording_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:record"))],
)
async def get_recording_detail(
    request: Request,
    recording_id: int,
    query_db: Session = Depends(get_db),
):
    try:
        detail = DesktopCaseService.recording_detail_services(query_db, recording_id)
        if detail is None:
            return ResponseUtil.failure(msg="录制会话不存在")
        return ResponseUtil.success(data=detail.model_dump(mode="json", by_alias=True))
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/recording/event/update",
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:desktopCase:edit", "hrm:desktopCase:record"], False))],
)
@log_decorator(title="桌面录制步骤编辑", business_type=2)
async def update_recording_event(
    request: Request,
    update_request: DesktopRecordingEventUpdateRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = DesktopCaseService.update_recording_event_services(
            query_db,
            update_request,
            user_name=current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/recording/replay",
    dependencies=[Depends(CheckUserInterfaceAuth(["hrm:desktopCase:run", "hrm:desktopCase:record"], False))],
)
@log_decorator(title="桌面录制回放", business_type=0)
async def replay_recording(
    request: Request,
    replay_request: DesktopRecordingReplayRequestModel,
    query_db: Session = Depends(get_db),
):
    try:
        result = await DesktopCaseService.replay_recording_services(query_db, replay_request)
        if result.is_success:
            return ResponseUtil.success(msg=result.message, data=result.result)
        return ResponseUtil.failure(msg=result.message, data=result.result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@desktopCaseController.post(
    "/recording/apply",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:edit"))],
)
@log_decorator(title="录制应用到桌面用例", business_type=2)
async def apply_recording(
    request: Request,
    apply_request: DesktopRecordingApplyRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = DesktopCaseService.apply_recording_to_case_services(
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


@desktopCaseController.post(
    "/recording/save-as-case",
    dependencies=[Depends(CheckUserInterfaceAuth("hrm:desktopCase:add"))],
)
@log_decorator(title="录制保存为桌面用例", business_type=1)
async def save_recording_as_case(
    request: Request,
    save_request: DesktopRecordingSaveCaseRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    try:
        result = DesktopCaseService.save_recording_as_case_services(
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
