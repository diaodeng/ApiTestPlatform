import json
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from config.database import SessionLocal
from config.get_db import get_db
from context.request_context import get_current_trace_id, trace_context
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_log_pull_vo import (
    TicketLogErrorsRequestModel,
    TicketLogPrepareRequestModel,
    TicketLogPullContentQueryModel,
    TicketLogPullCreateModel,
    TicketLogPullProjectVendorMapQueryModel,
    TicketLogPullProjectVendorMapUpsertModel,
    TicketLogPullQueryModel,
    TicketLogPullStorageConfigModel,
    TicketLogPullStoreConfigQueryModel,
    TicketLogSearchRequestModel,
    TicketLogSearchTimeRequestModel,
)
from modules.ticket.entity.vo.ticket_vo import (
    KnowledgeArticleModel,
    KnowledgeArticleQueryModel,
    TicketAiAnalysisRequestModel,
    TicketAiAnalysisTaskQueryModel,
    TicketAiRepoMappingCreateModel,
    TicketAiRepoMappingQueryModel,
    TicketAiRepoMappingUpdateModel,
    TicketAssignModel,
    TicketBatchReclassifyRequestModel,
    TicketCommentCreateModel,
    TicketCreateModel,
    TicketEmbeddingRebuildRequestModel,
    TicketEventCreateModel,
    TicketExternalSyncUpsertModel,
    TicketMessageCreateModel,
    TicketQueryModel,
    TicketRcaModel,
    TicketSimilarityConfigModel,
    TicketSnapshotModel,
    TicketStatisticsQueryModel,
    TicketStatusChangeModel,
    TicketSyncAckRequestModel,
    TicketSyncGroupPushSendModel,
    TicketSyncPersonReminderPreviewModel,
    TicketSyncPersonReminderRunModel,
    TicketSyncPullQueryModel,
    TicketSyncSummaryRunModel,
    TicketUpdateModel,
    TicketUserOptionQueryModel,
    WorkflowStatusModel,
    WorkflowTransitionModel,
)
from modules.ticket.service.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ticket_import_service import TicketImportService
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.ticket_log_service import LogService
from modules.ticket.service.ticket_message_sync_service import TicketMessageSyncService
from modules.ticket.service.ticket_service import TicketService
from modules.ticket.service.ticket_sync_service import TicketSyncService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketCrudController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])

@ticketCrudController.get("/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def get_ticket_list(
    request: Request, query: TicketQueryModel = Depends(TicketQueryModel.as_query), query_db: Session = Depends(get_db)
):
    """
    获取工单列表接口。
    :param request: 请求对象
    :param query: 工单查询条件，支持工单状态、工单号、处理状态、项目、商家、模块、优先级、来源和关键字筛选
    :param query_db: 数据库会话
    :return: 工单分页列表
    """
    try:
        query_result = TicketService.get_ticket_list_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get("/import/template", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:import"))])
async def download_ticket_import_template(request: Request):
    """
    下载工单 Excel 导入模板接口。
    :param request: 请求对象
    :return: 工单导入模板 Excel 文件
    """
    try:
        filename = "工单导入模板.xlsx"
        return Response(
            content=TicketImportService.build_import_template(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "download-filename": quote(filename),
            },
        )
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post("/import", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:import"))])
@log_decorator(title="工单导入", business_type=1)
async def import_ticket_excel(
    request: Request,
    file: UploadFile = File(...),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    导入工单 Excel 接口。
    :param request: 请求对象
    :param file: 飞书多维表格导出的 Excel 文件或系统导入模板文件
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入导入审计信息
    :return: 导入汇总，包含重复工单号和失败行
    """
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return ResponseUtil.failure(msg="仅支持 xlsx 文件")
        result = await TicketImportService.import_excel(query_db, await file.read(), current_user)
        return ResponseUtil.success(data=result, msg="导入完成")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get("/search/natural-language", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def search_ticket_natural_language(
    request: Request,
    keyword: str,
    limit: int = 20,
    query_db: Session = Depends(get_db),
):
    """
    自然语言搜索工单接口。
    :param request: 请求对象
    :param keyword: 自然语言搜索文本
    :param limit: 返回数量限制
    :param query_db: 数据库会话
    :return: 按相关性排序的工单列表
    """
    try:
        return ResponseUtil.success(data=TicketEmbeddingService.search_tickets(query_db, keyword, limit))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketCrudController.post("", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:add"))])
@log_decorator(title="工单管理", business_type=1)
async def add_ticket(
    request: Request,
    add_ticket_object: TicketCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单接口。
    :param request: 请求对象
    :param add_ticket_object: 工单标题、描述、所属项目ID、所属模块ID、1线人员、内部负责人、优先级、来源和扩展上下文
    :param query_db: 数据库会话，仅用于操作日志记录；保存逻辑在线程池独立会话中执行
    :param current_user: 当前登录用户，用于写入提单人和审计信息
    :return: 新增结果
    """
    try:
        _ = query_db
        result = await run_in_threadpool(TicketService.create_ticket_with_independent_session, add_ticket_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

@ticketCrudController.put("", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:edit"))])
@log_decorator(title="工单管理", business_type=2)
async def edit_ticket(
    request: Request,
    edit_ticket_object: TicketUpdateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑工单接口。
    :param request: 请求对象
    :param edit_ticket_object: 工单基础字段、1线人员、内部负责人、标签、扩展上下文和 AI 分析预留字段
    :param query_db: 数据库会话，仅用于操作日志记录；保存逻辑在线程池独立会话中执行
    :param current_user: 当前登录用户，用于写入更新人
    :return: 编辑结果
    """
    try:
        _ = query_db
        result = await run_in_threadpool(TicketService.update_ticket_with_independent_session, edit_ticket_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/translate-description",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:edit"))],
)
@log_decorator(title="工单描述翻译", business_type=2)
async def translate_ticket_description(
    request: Request,
    ticket_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    手动翻译工单描述接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入审计信息
    :return: 翻译后的工单详情
    """
    try:
        result = TicketService.translate_ticket_description_services(query_db, ticket_id, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.delete("/{ticket_id:int}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:remove"))])
@log_decorator(title="工单管理", business_type=3)
async def delete_ticket(
    request: Request,
    ticket_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除工单接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入删除审计信息
    :return: 删除结果
    """
    try:
        result = TicketService.delete_ticket(query_db, ticket_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get("/{ticket_id:int}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:query"))])
async def get_ticket_detail(request: Request, ticket_id: int, query_db: Session = Depends(get_db)):
    """
    获取工单详情接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :return: 工单详情
    """
    try:
        result = TicketService.get_ticket_detail_services(query_db, ticket_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="工单不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketCrudController.post(
    "/{ticket_id:int}/assign", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:assign"))]
)
@log_decorator(title="工单指派", business_type=2)
async def assign_ticket(
    request: Request,
    ticket_id: int,
    assign_object: TicketAssignModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    指派工单接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param assign_object: 目标处理人ID、名称和指派原因
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入指派人
    :return: 指派结果
    """
    try:
        result = TicketService.assign_ticket(query_db, ticket_id, assign_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/status", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:status"))]
)
@log_decorator(title="工单状态流转", business_type=2)
async def change_ticket_status(
    request: Request,
    ticket_id: int,
    status_object: TicketStatusChangeModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    工单状态流转接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param status_object: 目标状态、流转说明、根因、解决方案和是否真实问题
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入操作人
    :return: 状态流转结果
    """
    try:
        result = TicketService.change_ticket_status(query_db, ticket_id, status_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/comments", dependencies=[Depends(CheckUserInterfaceAuth("ticket:comment:add"))]
)
async def add_ticket_comment(
    request: Request,
    ticket_id: int,
    comment_object: TicketCommentCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单评论接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param comment_object: 评论内容和是否内部评论
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入评论人
    :return: 评论结果
    """
    try:
        result = TicketService.add_comment(query_db, ticket_id, comment_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get(
    "/{ticket_id:int}/comments", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:timeline"))]
)
async def list_ticket_comments(request: Request, ticket_id: int, query_db: Session = Depends(get_db)):
    """
    查询工单评论列表接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :return: 工单评论列表
    """
    try:
        result = await run_in_threadpool(TicketService.list_comment_services, query_db, ticket_id)
        return ResponseUtil.success(data=result) if result is not None else ResponseUtil.failure(msg="工单不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post("/{ticket_id:int}/events", dependencies=[Depends(CheckUserInterfaceAuth("ticket:event:add"))])
async def add_ticket_event(
    request: Request,
    ticket_id: int,
    event_object: TicketEventCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单事件接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param event_object: 事件类型、说明和结构化事件数据，用于排查过程、日志分析、复现、修复和验证记录
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入操作人
    :return: 事件记录结果
    """
    try:
        result = TicketService.add_event(query_db, ticket_id, event_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get(
    "/{ticket_id:int}/timeline", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:timeline"))]
)
async def get_ticket_timeline(request: Request, ticket_id: int, query_db: Session = Depends(get_db)):
    """
    获取工单时间线接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :return: 状态历史、指派历史、事件和 RCA
    """
    try:
        result = TicketService.get_timeline_services(query_db, ticket_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="工单不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get(
    "/{ticket_id:int}/messages", dependencies=[Depends(CheckUserInterfaceAuth("ticket:message:list"))]
)
async def get_ticket_messages(request: Request, ticket_id: int, query_db: Session = Depends(get_db)):
    """
    获取工单协同消息接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :return: 工单消息流、ACR快照和相似工单推荐
    """
    try:
        result = TicketService.get_messages_services(query_db, ticket_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="工单不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/log-pulls",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:add"))],
)
async def create_ticket_log_pull_manage(
    request: Request,
    create_object: TicketLogPullCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增日志拉取管理记录接口。
    :param request: 请求对象
    :param create_object: 日志拉取参数，关联工单可选
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入申请人
    :return: 创建结果
    """
    try:
        result = await run_in_threadpool(
            TicketLogPullService.create_log_pull_services,
            query_db,
            create_object.ticket_id,
            create_object,
            current_user,
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/messages", dependencies=[Depends(CheckUserInterfaceAuth("ticket:message:add"))]
)
async def add_ticket_message(
    request: Request,
    ticket_id: int,
    message_object: TicketMessageCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单协同消息接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param message_object: 角色、消息类型、内容、附件和是否立即发起 AI 追问
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入消息创建人
    :return: 消息保存结果及可选 AI 任务结果
    """
    try:
        result = TicketService.add_message(query_db, ticket_id, message_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/snapshots", dependencies=[Depends(CheckUserInterfaceAuth("ticket:snapshot:add"))]
)
async def add_ticket_snapshot(
    request: Request,
    ticket_id: int,
    snapshot_object: TicketSnapshotModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增工单 ACR 快照接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param snapshot_object: 摘要、根因、解决方案、预防、风险和负责人
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入快照创建人
    :return: 快照保存结果
    """
    try:
        result = TicketService.create_snapshot(query_db, ticket_id, snapshot_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.post(
    "/{ticket_id:int}/knowledge/extract",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:add"))],
)
async def extract_ticket_knowledge(
    request: Request,
    ticket_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    从工单自动生成知识库案例接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入知识库创建人
    :return: 知识库案例生成结果
    """
    try:
        result = TicketService.create_knowledge_from_ticket(query_db, ticket_id, current_user)
        if result.is_success:
            query_db.commit()
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        query_db.rollback()
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketCrudController.get(
    "/users/options",
    dependencies=[Depends(CheckUserInterfaceAuth(["ticket:ticket:assign", "ticket:workflow:edit"], False))],
)
async def get_ticket_user_options(
    request: Request,
    query: TicketUserOptionQueryModel = Depends(TicketUserOptionQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单指派用户选择器选项接口。
    :param request: 请求对象
    :param query: 用户名、昵称或手机号关键字，以及返回数量限制
    :param query_db: 数据库会话
    :return: 可指派用户选项
    """
    try:
        return ResponseUtil.success(data=TicketService.get_user_options_services(query_db, query.keyword, query.limit))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get("/projects/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def get_ticket_project_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单可选测试项目列表接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 项目选项列表
    """
    try:
        return ResponseUtil.success(data=TicketService.get_project_options_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get("/modules/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def get_ticket_module_options(
    request: Request,
    projectId: int | None = None,
    query_db: Session = Depends(get_db),
):
    """
    获取工单可选测试模块列表接口。
    :param request: 请求对象
    :param project_id: 项目ID；传入后仅返回当前项目下的模块
    :param query_db: 数据库会话
    :return: 模块选项列表，包含模块ID、名称和模块业务码
    """
    try:
        return ResponseUtil.success(data=TicketService.get_module_options_services(query_db, projectId))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketCrudController.get(
    "/stat-classification/options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))],
)
async def get_ticket_stat_classification_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单分类统计枚举选项接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 工单类型、根因分类、解决方式和关闭结果选项
    """
    try:
        return ResponseUtil.success(data=TicketSyncService.get_ticket_stat_classification_options(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

