from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_vo import (
    TicketReleaseBatchUpdateModel,
    TicketVersionStatisticsQueryModel,
)
from modules.ticket.service.core.ticket_release_service import TicketReleaseService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketReleaseController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])


@ticketReleaseController.post(
    "/release/batch",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:edit"))],
)
async def batch_update_ticket_release_fields(
    request: Request,
    payload: TicketReleaseBatchUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    批量维护工单版本治理字段。
    :param request: 请求对象
    :param payload: 批量维护参数
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 批量维护结果
    """
    try:
        result = await run_in_threadpool(
            TicketReleaseService.batch_update_release_fields,
            query_db,
            payload,
            current_user,
        )
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(data=result.result, msg=result.message)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))


@ticketReleaseController.get(
    "/release/statistics",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:statistics:list"))],
)
async def get_ticket_version_statistics(
    request: Request,
    query: TicketVersionStatisticsQueryModel = Depends(TicketVersionStatisticsQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单版本统计。
    :param request: 请求对象
    :param query: 版本统计查询条件
    :param query_db: 数据库会话
    :return: 版本统计结果
    """
    try:
        statistics = await run_in_threadpool(
            TicketReleaseService.get_version_statistics,
            query_db,
            query,
        )
        return ResponseUtil.success(data=statistics)
    except Exception as exc:
        logger.exception(exc)
        return ResponseUtil.error(msg=str(exc))
