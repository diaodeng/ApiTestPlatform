from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_vo import (
    TicketAiAnalysisRequestModel,
    TicketAiAnalysisTaskQueryModel,
    TicketAiRepoMappingCreateModel,
    TicketAiRepoMappingQueryModel,
    TicketAiRepoMappingUpdateModel,
)
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketAiController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])


@ticketAiController.get(
    "/ai/repo-mappings",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:list"))],
)
async def get_ticket_ai_repo_mappings(
    request: Request,
    query: TicketAiRepoMappingQueryModel = Depends(TicketAiRepoMappingQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单 AI 仓库映射列表接口。
    :param request: 请求对象
    :param query: 项目、版本、启用状态和关键字筛选参数
    :param query_db: 数据库会话
    :return: AI 仓库映射分页列表
    """
    try:
        result = await run_in_threadpool(TicketAiAnalysisService.list_repo_mapping_services, query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.post("/ai/repo-mappings", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:add"))])
@log_decorator(title="工单AI映射", business_type=1)
async def add_ticket_ai_repo_mapping(
    request: Request,
    mapping_object: TicketAiRepoMappingCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单 AI 仓库映射接口。
    :param request: 请求对象
    :param mapping_object: 项目、版本、仓库地址、分支和工作区配置
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 新增结果
    """
    try:
        result = TicketAiAnalysisService.save_repo_mapping_services(query_db, mapping_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.put("/ai/repo-mappings", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:edit"))])
@log_decorator(title="工单AI映射", business_type=2)
async def edit_ticket_ai_repo_mapping(
    request: Request,
    mapping_object: TicketAiRepoMappingUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑工单 AI 仓库映射接口。
    :param request: 请求对象
    :param mapping_object: 映射ID及仓库配置
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 编辑结果
    """
    try:
        result = TicketAiAnalysisService.save_repo_mapping_services(query_db, mapping_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.delete(
    "/ai/repo-mappings/{mapping_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:remove"))],
)
@log_decorator(title="工单AI映射", business_type=3)
async def delete_ticket_ai_repo_mapping(
    request: Request,
    mapping_id: int,
    query_db: Session = Depends(get_db),
):
    """
    删除工单 AI 仓库映射接口。
    :param request: 请求对象
    :param mapping_id: 映射ID
    :param query_db: 数据库会话
    :return: 删除结果
    """
    try:
        result = TicketAiAnalysisService.delete_repo_mapping_services(query_db, mapping_id)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.get(
    "/{ticket_id:int}/ai-analysis/tasks",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:analysis:list"))],
)
async def get_ticket_ai_analysis_tasks(
    request: Request,
    ticket_id: int,
    query: TicketAiAnalysisTaskQueryModel = Depends(TicketAiAnalysisTaskQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单 AI 分析任务列表接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query: 状态、版本和分页参数
    :param query_db: 数据库会话
    :return: AI 分析任务分页列表
    """
    try:
        result = TicketAiAnalysisService.get_task_list_services(query_db, ticket_id, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.post(
    "/{ticket_id:int}/ai-analysis/tasks/{task_id}/retry",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:analysis:run"))],
)
@log_decorator(title="工单AI分析重试", business_type=1)
async def retry_ticket_ai_analysis_task(
    request: Request,
    ticket_id: int,
    task_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    重新提交指定 AI 分析任务接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param task_id: AI 分析任务ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 重试结果
    """
    try:
        result = TicketAiAnalysisService.retry_analysis_task_services(query_db, ticket_id, task_id, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketAiController.post(
    "/{ticket_id:int}/ai-analysis",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:analysis:run"))],
)
@log_decorator(title="工单AI分析", business_type=1)
async def create_ticket_ai_analysis(
    request: Request,
    ticket_id: int,
    analysis_object: TicketAiAnalysisRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    提交工单 AI 分析任务接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param analysis_object: 仓库映射、版本、日志记录、额外说明和 Agent 选择参数
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 创建结果
    """
    try:
        result = TicketAiAnalysisService.create_analysis_task_services(
            query_db, ticket_id, analysis_object, current_user
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
