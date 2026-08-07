from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_version_vo import (
    TicketVersionCreateModel,
    TicketVersionOptionsQueryModel,
    TicketVersionQueryModel,
    TicketVersionReleaseCreateModel,
    TicketVersionReleaseUpdateModel,
    TicketVersionUpdateModel,
)
from modules.ticket.service.core.ticket_version_service import TicketVersionService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketVersionController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])


@ticketVersionController.get("/versions/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:list"))])
async def list_ticket_versions(
    request: Request,
    query: TicketVersionQueryModel = Depends(TicketVersionQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """分页查询项目版本中心。"""
    try:
        result = await run_in_threadpool(TicketVersionService.list_version_services, query_db, query)
        return ResponseUtil.success(model_content=result) if query.is_page else ResponseUtil.success(data=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.get("/versions/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def list_ticket_version_options(
    request: Request,
    query: TicketVersionOptionsQueryModel = Depends(TicketVersionOptionsQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """按项目返回统一版本选项。"""
    try:
        result = await run_in_threadpool(
            TicketVersionService.list_version_options,
            query_db,
            query.project_id,
            query.include_discovered,
        )
        return ResponseUtil.success(data=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.post("/versions", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:add"))])
async def add_ticket_version(
    request: Request,
    payload: TicketVersionCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """创建人工维护的项目版本。"""
    try:
        result = await run_in_threadpool(TicketVersionService.create_version, query_db, payload, current_user)
        return (
            ResponseUtil.success(data=result.result, msg=result.message)
            if result.is_success
            else ResponseUtil.failure(msg=result.message)
        )
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.put("/versions", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:edit"))])
async def edit_ticket_version(
    request: Request,
    payload: TicketVersionUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """更新项目版本维护信息。"""
    try:
        result = await run_in_threadpool(TicketVersionService.update_version, query_db, payload, current_user)
        return (
            ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)
        )
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.get(
    "/versions/{version_id:int}/releases", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:list"))]
)
async def list_ticket_version_releases(request: Request, version_id: int, query_db: Session = Depends(get_db)):
    """查询指定版本的发布历史。"""
    try:
        result = await run_in_threadpool(TicketVersionService.list_release_services, query_db, version_id)
        return ResponseUtil.success(data=result)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.post(
    "/version-releases", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:release"))]
)
async def add_ticket_version_release(
    request: Request,
    payload: TicketVersionReleaseCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """登记版本发布事实。"""
    try:
        result = await run_in_threadpool(TicketVersionService.save_release, query_db, payload, current_user)
        return (
            ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)
        )
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketVersionController.put(
    "/version-releases", dependencies=[Depends(CheckUserInterfaceAuth("ticket:version:release"))]
)
async def edit_ticket_version_release(
    request: Request,
    payload: TicketVersionReleaseUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """更新版本发布事实。"""
    try:
        result = await run_in_threadpool(TicketVersionService.save_release, query_db, payload, current_user)
        return (
            ResponseUtil.success(msg=result.message) if result.is_success else ResponseUtil.failure(msg=result.message)
        )
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))
