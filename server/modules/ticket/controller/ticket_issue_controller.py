from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_issue_vo import (
    TicketIssueBindModel,
    TicketIssueCreateAndBindModel,
    TicketIssueCreateModel,
    TicketIssueQueryModel,
    TicketIssueSimilarBindModel,
    TicketIssueUpdateModel,
    TicketRelationCreateModel,
)
from modules.ticket.service.issue.ticket_issue_service import TicketIssueService
from modules.ticket.service.issue.ticket_relation_service import TicketRelationService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketIssueController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])


@ticketIssueController.get("/issues/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:list"))])
async def get_ticket_issue_list(
    request: Request,
    query: TicketIssueQueryModel = Depends(TicketIssueQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    查询问题实例列表接口。
    :param request: 请求对象
    :param query: 问题实例查询条件
    :param query_db: 数据库会话
    :return: 问题实例分页列表
    """
    try:
        query_result = TicketIssueService.get_issue_list_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.get(
    "/issues/{issue_id:int}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:query"))],
)
async def get_ticket_issue_detail(request: Request, issue_id: int, query_db: Session = Depends(get_db)):
    """
    查询问题实例详情接口。
    :param request: 请求对象
    :param issue_id: 问题实例ID
    :param query_db: 数据库会话
    :return: 问题实例详情和绑定工单列表
    """
    try:
        result = TicketIssueService.get_issue_detail_services(query_db, issue_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="问题实例不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post("/issues", dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:add"))])
@log_decorator(title="问题实例", business_type=1)
async def add_ticket_issue(
    request: Request,
    issue_object: TicketIssueCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    创建问题实例接口。
    :param request: 请求对象
    :param issue_object: 创建参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 创建结果
    """
    try:
        result = TicketIssueService.create_issue(query_db, issue_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.put("/issues", dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:edit"))])
@log_decorator(title="问题实例", business_type=2)
async def edit_ticket_issue(
    request: Request,
    issue_object: TicketIssueUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑问题实例接口。
    :param request: 请求对象
    :param issue_object: 编辑参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 编辑结果
    """
    try:
        result = TicketIssueService.update_issue(query_db, issue_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post(
    "/{ticket_id:int}/issue/bind",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:bind"))],
)
@log_decorator(title="工单问题归因", business_type=2)
async def bind_ticket_issue(
    request: Request,
    ticket_id: int,
    bind_object: TicketIssueBindModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    绑定工单到已有问题实例接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param bind_object: 绑定参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 绑定结果
    """
    try:
        result = TicketIssueService.bind_ticket_to_issue(query_db, ticket_id, bind_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post(
    "/{ticket_id:int}/issue/create-and-bind",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:add"))],
)
@log_decorator(title="工单问题归因", business_type=1)
async def create_ticket_issue_and_bind(
    request: Request,
    ticket_id: int,
    issue_object: TicketIssueCreateAndBindModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    创建问题实例并绑定当前工单接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param issue_object: 创建并绑定参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 绑定结果
    """
    try:
        result = TicketIssueService.create_issue_and_bind(query_db, ticket_id, issue_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post(
    "/{ticket_id:int}/issue/bind-from-similar",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:bind"))],
)
@log_decorator(title="相似工单问题归因", business_type=2)
async def bind_ticket_issue_from_similar(
    request: Request,
    ticket_id: int,
    bind_object: TicketIssueSimilarBindModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    从相似工单确认归因接口。
    :param request: 请求对象
    :param ticket_id: 当前工单ID
    :param bind_object: 相似工单参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 绑定结果
    """
    try:
        result = TicketIssueService.bind_from_similar(query_db, ticket_id, bind_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post(
    "/{ticket_id:int}/issue/unbind",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:issue:remove"))],
)
@log_decorator(title="工单问题归因", business_type=2)
async def unbind_ticket_issue(
    request: Request,
    ticket_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    解除工单问题归因接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 解绑结果
    """
    try:
        result = TicketIssueService.unbind_ticket_issue(query_db, ticket_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.post("/relations", dependencies=[Depends(CheckUserInterfaceAuth("ticket:relation:add"))])
@log_decorator(title="工单补充关系", business_type=1)
async def add_ticket_relation(
    request: Request,
    relation_object: TicketRelationCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单补充关系接口。
    :param request: 请求对象
    :param relation_object: 关系参数
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 创建结果
    """
    try:
        result = TicketRelationService.create_relation(query_db, relation_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.put(
    "/relations/{relation_id:int}/confirm",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:relation:edit"))],
)
@log_decorator(title="工单补充关系", business_type=2)
async def confirm_ticket_relation(
    request: Request,
    relation_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    确认工单补充关系接口。
    :param request: 请求对象
    :param relation_id: 关系ID
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 确认结果
    """
    try:
        result = TicketRelationService.confirm_relation(query_db, relation_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketIssueController.delete(
    "/relations/{relation_id:int}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:relation:remove"))],
)
@log_decorator(title="工单补充关系", business_type=3)
async def delete_ticket_relation(
    request: Request,
    relation_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除工单补充关系接口。
    :param request: 请求对象
    :param relation_id: 关系ID
    :param query_db: 数据库会话
    :param current_user: 当前用户
    :return: 删除结果
    """
    try:
        result = TicketRelationService.delete_relation(query_db, relation_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
