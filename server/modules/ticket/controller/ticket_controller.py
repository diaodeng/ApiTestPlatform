from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy.orm import Session

from config.get_db import get_db
from module_admin.annotation.log_annotation import log_decorator
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_log_pull_vo import (
    TicketLogPullContentQueryModel,
    TicketLogPullCreateModel,
    TicketLogPullQueryModel,
    TicketLogPullStorageConfigModel,
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
    TicketCommentCreateModel,
    TicketCreateModel,
    TicketEventCreateModel,
    TicketExternalSyncUpsertModel,
    TicketMessageCreateModel,
    TicketQueryModel,
    TicketRcaModel,
    TicketSnapshotModel,
    TicketStatisticsQueryModel,
    TicketStatusChangeModel,
    TicketSyncAckRequestModel,
    TicketSyncPullQueryModel,
    TicketUpdateModel,
    TicketUserOptionQueryModel,
    WorkflowStatusModel,
    WorkflowTransitionModel,
)
from modules.ticket.service.ticket_ai_analysis_service import TicketAiAnalysisService
from modules.ticket.service.ticket_embedding_service import TicketEmbeddingService
from modules.ticket.service.ticket_import_service import TicketImportService
from modules.ticket.service.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.ticket_service import TicketService
from modules.ticket.service.ticket_sync_service import TicketSyncService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])


@ticketController.get("/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
async def get_ticket_list(
    request: Request, query: TicketQueryModel = Depends(TicketQueryModel.as_query), query_db: Session = Depends(get_db)
):
    """
    获取工单列表接口。
    :param request: 请求对象
    :param query: 工单查询条件，支持状态、项目、商家、模块、优先级、来源和关键字筛选
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


@ticketController.get("/import/template", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:import"))])
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


@ticketController.post("/import", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:import"))])
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


@ticketController.get("/search/natural-language", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
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


@ticketController.get(
    "/log-pull/storage-config",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:config"))],
)
async def get_ticket_log_pull_storage_config(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单日志拉取存储配置接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 日志压缩包本地/FTP 保存与轮询配置
    """
    try:
        return ResponseUtil.success(data=TicketLogPullService.get_storage_config_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
    "/log-pull/vendor-store-options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_vendor_store_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取日志拉取页面商家/门店联动选项接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 脱敏后的商家与门店选项
    """
    try:
        result = TicketLogPullService.get_vendor_store_options_services(query_db)
        return ResponseUtil.success(data=result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.put(
    "/log-pull/storage-config",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:config"))],
)
async def save_ticket_log_pull_storage_config(
    request: Request,
    config_object: TicketLogPullStorageConfigModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存工单日志拉取存储配置接口。
    :param request: 请求对象
    :param config_object: 本地目录、FTP 连接、轮询和压缩入库配置
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入配置审计信息
    :return: 保存结果；当前版本统一改为通过系统参数配置维护
    """
    try:
        return ResponseUtil.failure(msg="请前往参数配置维护 ticket.logPull.external / ticket.logPull.storage")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:add"))])
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
    :param add_ticket_object: 工单标题、描述、所属项目ID、所属模块ID、优先级、来源和扩展上下文
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入提单人和审计信息
    :return: 新增结果
    """
    try:
        result = TicketService.create_ticket(query_db, add_ticket_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/sync/external", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:external"))])
async def sync_external_ticket(
    request: Request,
    sync_object: TicketExternalSyncUpsertModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    外部工单系统同步数据入库接口。
    """
    try:
        result = TicketSyncService.sync_external_ticket(query_db, sync_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get("/sync/pending", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:pull"))])
async def pull_pending_sync_tickets(
    request: Request,
    query: TicketSyncPullQueryModel = Depends(),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    内网系统拉取未同步或更新后的工单数据。
    """
    try:
        return ResponseUtil.success(data=TicketSyncService.pull_pending_tickets(query_db, query, current_user))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/sync/ack", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:pull"))])
async def ack_sync_tickets(
    request: Request,
    ack_object: TicketSyncAckRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    内网系统回执本次拉取数据的交付状态。
    """
    try:
        result = TicketSyncService.ack_sync_delivery(query_db, ack_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.put("", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:edit"))])
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
    :param edit_ticket_object: 工单基础字段、标签、扩展上下文和 AI 分析预留字段
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入更新人
    :return: 编辑结果
    """
    try:
        result = TicketService.update_ticket(query_db, edit_ticket_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.delete("/{ticket_id:int}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:remove"))])
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


@ticketController.get("/{ticket_id:int}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:query"))])
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


@ticketController.get(
    "/log-pulls/{record_id}/content",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_content(
    request: Request,
    record_id: int,
    query: TicketLogPullContentQueryModel = Depends(TicketLogPullContentQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取日志拉取记录文本内容接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param query: 查看日志范围参数，支持开始/结束时间或时间点前后范围
    :param query_db: 数据库会话
    :return: 解压后的日志文本内容
    """
    try:
        result = TicketLogPullService.get_log_pull_content_services(query_db, record_id, query)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="日志拉取记录不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
    "/log-pulls-by-ticket",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_list(
    request: Request,
    query: TicketLogPullQueryModel = Depends(TicketLogPullQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单日志拉取记录列表接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query: 分页和状态筛选参数
    :param query_db: 数据库会话
    :return: 日志拉取记录分页列表
    """
    try:
        result = TicketLogPullService.list_log_pull_records_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
    "/log-pulls",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_manage_list(
    request: Request,
    query: TicketLogPullQueryModel = Depends(TicketLogPullQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取日志拉取管理列表接口。
    :param request: 请求对象
    :param query: 日志拉取查询条件，支持工单、状态和关键字筛选
    :param query_db: 数据库会话
    :return: 日志拉取分页列表
    """
    try:
        result = TicketLogPullService.list_log_pull_management_records_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post(
    "/{ticket_id:int}/log-pulls",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:add"))],
)
async def create_ticket_log_pull(
    request: Request,
    ticket_id: int,
    create_object: TicketLogPullCreateModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    提交工单日志拉取申请接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param create_object: 日志拉取参数，包含 vendor/store/pos、命令内容和时间范围
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入申请人
    :return: 创建结果
    """
    try:
        result = TicketLogPullService.create_log_pull_services(query_db, ticket_id, create_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post(
    "/log-pulls/{record_id}/retry",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:add"))],
)
async def retry_ticket_log_pull(
    request: Request,
    record_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    基于原参数重新提交日志拉取任务接口。
    :param request: 请求对象
    :param record_id: 原日志拉取记录ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入审计信息
    :return: 重新提交结果
    """
    try:
        result = TicketLogPullService.retry_log_pull_services(query_db, record_id, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post(
    "/log-pulls/{record_id}/redownload",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:add"))],
)
async def redownload_ticket_log_pull(
    request: Request,
    record_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    重新下载日志压缩包接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入审计信息
    :return: 重新下载结果
    """
    try:
        result = TicketLogPullService.redownload_log_pull_services(query_db, record_id, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post(
    "/log-pulls/{record_id}/reextract",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:add"))],
)
async def reextract_ticket_log_pull(
    request: Request,
    record_id: int,
    query: TicketLogPullContentQueryModel = Depends(TicketLogPullContentQueryModel.as_query),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    按新的时间范围重新截取日志内容接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param query: 查看日志时使用的时间范围参数
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入审计信息
    :return: 重新截取结果
    """
    try:
        result = TicketLogPullService.reextract_log_pull_services(query_db, record_id, query, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
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
        result = TicketAiAnalysisService.list_repo_mapping_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/ai/repo-mappings", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:add"))])
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


@ticketController.put("/ai/repo-mappings", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ai:mapping:edit"))])
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


@ticketController.delete(
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


@ticketController.get(
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


@ticketController.post(
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


@ticketController.post(
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


@ticketController.post("/{ticket_id:int}/assign", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:assign"))])
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


@ticketController.post("/{ticket_id:int}/status", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:status"))])
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


@ticketController.post("/{ticket_id:int}/comments", dependencies=[Depends(CheckUserInterfaceAuth("ticket:comment:add"))])
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


@ticketController.post("/{ticket_id:int}/events", dependencies=[Depends(CheckUserInterfaceAuth("ticket:event:add"))])
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


@ticketController.get("/{ticket_id:int}/timeline", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:timeline"))])
async def get_ticket_timeline(request: Request, ticket_id: int, query_db: Session = Depends(get_db)):
    """
    获取工单时间线接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param query_db: 数据库会话
    :return: 状态历史、指派历史、评论、事件和 RCA
    """
    try:
        result = TicketService.get_timeline_services(query_db, ticket_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="工单不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get("/{ticket_id:int}/messages", dependencies=[Depends(CheckUserInterfaceAuth("ticket:message:list"))])
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


@ticketController.post(
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
        result = TicketLogPullService.create_log_pull_services(query_db, create_object.ticket_id, create_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/{ticket_id:int}/messages", dependencies=[Depends(CheckUserInterfaceAuth("ticket:message:add"))])
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


@ticketController.post("/{ticket_id:int}/snapshots", dependencies=[Depends(CheckUserInterfaceAuth("ticket:snapshot:add"))])
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


@ticketController.post(
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


@ticketController.put("/{ticket_id:int}/rca", dependencies=[Depends(CheckUserInterfaceAuth("ticket:rca:edit"))])
async def upsert_ticket_rca(
    request: Request,
    ticket_id: int,
    rca_object: TicketRcaModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存工单 RCA 接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param rca_object: 现象、影响范围、复现步骤、排查过程、根因、修复方案、验证方式和预防方案
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入创建人
    :return: RCA 保存结果
    """
    try:
        result = TicketService.upsert_rca(query_db, ticket_id, rca_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get("/workflow/config", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:list"))])
async def get_ticket_workflow(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单工作流配置接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 状态列表和流转配置
    """
    try:
        return ResponseUtil.success(data=TicketService.get_workflow_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/workflow/status", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:edit"))])
async def save_workflow_status(
    request: Request,
    status_object: WorkflowStatusModel,
    query_db: Session = Depends(get_db),
):
    """
    保存工作流状态节点接口。
    :param request: 请求对象
    :param status_object: 状态ID、编码、名称、是否开始状态、是否结束状态和排序
    :param query_db: 数据库会话
    :return: 保存结果
    """
    try:
        result = TicketService.save_workflow_status(query_db, status_object)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.delete(
    "/workflow/status/{status_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:remove"))]
)
async def delete_workflow_status(request: Request, status_id: int, query_db: Session = Depends(get_db)):
    """
    删除工作流状态节点接口。
    :param request: 请求对象
    :param status_id: 状态节点ID
    :param query_db: 数据库会话
    :return: 删除结果；已被工单、历史或流转规则引用时会拒绝删除
    """
    try:
        result = TicketService.delete_workflow_status(query_db, status_id)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/workflow/transition", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:edit"))])
async def save_workflow_transition(
    request: Request, transition_object: WorkflowTransitionModel, query_db: Session = Depends(get_db)
):
    """
    保存工作流流转规则接口。
    :param request: 请求对象
    :param transition_object: 流转ID、原状态、目标状态、允许角色、是否需要说明和是否需要解决方案
    :param query_db: 数据库会话
    :return: 保存结果
    """
    try:
        result = TicketService.save_workflow_transition(query_db, transition_object)
        if result.is_success:
            return ResponseUtil.success(data=result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.delete(
    "/workflow/transition/{transition_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:workflow:remove"))]
)
async def delete_workflow_transition(request: Request, transition_id: int, query_db: Session = Depends(get_db)):
    """
    删除工作流流转规则接口。
    :param request: 请求对象
    :param transition_id: 流转规则ID
    :param query_db: 数据库会话
    :return: 删除结果
    """
    try:
        result = TicketService.delete_workflow_transition(query_db, transition_id)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
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


@ticketController.get("/projects/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
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


@ticketController.get("/modules/options", dependencies=[Depends(CheckUserInterfaceAuth("ticket:ticket:list"))])
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
    :return: 模块选项列表
    """
    try:
        return ResponseUtil.success(data=TicketService.get_module_options_services(query_db, projectId))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get("/statistics/overview", dependencies=[Depends(CheckUserInterfaceAuth("ticket:statistics:list"))])
async def get_ticket_statistics(
    request: Request,
    query: TicketStatisticsQueryModel = Depends(TicketStatisticsQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取工单统计接口。
    :param request: 请求对象
    :param query: 时间范围参数
    :param query_db: 数据库会话
    :return: 总量、平均处理耗时、状态分布、分类分布和人员处理量
    """
    try:
        statistics = TicketService.get_statistics_services(query_db, query.begin_time, query.end_time)
        return ResponseUtil.success(data=statistics)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get("/knowledge/list", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:list"))])
async def get_knowledge_list(
    request: Request,
    query: KnowledgeArticleQueryModel = Depends(KnowledgeArticleQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    获取知识库文章列表接口。
    :param request: 请求对象
    :param query: 文章标题、分类和关键字查询条件
    :param query_db: 数据库会话
    :return: 知识库文章分页列表
    """
    try:
        query_result = TicketService.get_knowledge_list_services(query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=query_result)
        return ResponseUtil.success(data=query_result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.post("/knowledge", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:add"))])
async def add_knowledge(
    request: Request,
    article_object: KnowledgeArticleModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    新增知识库文章接口。
    :param request: 请求对象
    :param article_object: 标题、内容、分类、标签和关联工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入创建人
    :return: 新增结果
    """
    try:
        result = TicketService.create_knowledge(query_db, article_object, current_user)
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.put("/knowledge", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:edit"))])
async def edit_knowledge(
    request: Request,
    article_object: KnowledgeArticleModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    编辑知识库文章接口。
    :param request: 请求对象
    :param article_object: 文章ID、标题、内容、分类、标签和关联工单ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 编辑结果
    """
    try:
        result = TicketService.update_knowledge(query_db, article_object, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.get(
    "/knowledge/{article_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:query"))],
)
async def get_knowledge_detail(request: Request, article_id: int, query_db: Session = Depends(get_db)):
    """
    获取知识库文章详情接口。
    :param request: 请求对象
    :param article_id: 文章ID
    :param query_db: 数据库会话
    :return: 文章详情
    """
    try:
        result = TicketService.get_knowledge_detail_services(query_db, article_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="知识库文章不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketController.delete(
    "/knowledge/{article_id}", dependencies=[Depends(CheckUserInterfaceAuth("ticket:knowledge:remove"))]
)
async def delete_knowledge(
    request: Request,
    article_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除知识库文章接口。
    :param request: 请求对象
    :param article_id: 文章ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 删除结果
    """
    try:
        result = TicketService.delete_knowledge(query_db, article_id, current_user)
        if result.is_success:
            return ResponseUtil.success(msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
