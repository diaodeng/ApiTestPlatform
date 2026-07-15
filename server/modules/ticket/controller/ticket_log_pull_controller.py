from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from config.get_db import get_db
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
from modules.ticket.service.log_pull.ticket_log_pull_service import TicketLogPullService
from modules.ticket.service.log_pull.ticket_log_service import LogService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketLogPullController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])

@ticketLogPullController.get(
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


@ticketLogPullController.get(
    "/log-pull/vendor-store-options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_vendor_store_options(
    request: Request,
    vendor_id: int | None = None,
    query_db: Session = Depends(get_db),
):
    """
    获取日志拉取页面商家/门店联动选项接口。
    :param request: 请求对象
    :param vendor_id: 可选商家ID，传入后只返回该商家对应的门店列表
    :param query_db: 数据库会话
    :return: 脱敏后的商家与门店选项
    """
    try:
        result = TicketLogPullService.get_vendor_store_options_services(query_db, vendor_id=vendor_id)
        return ResponseUtil.success(data=result.model_dump(by_alias=True))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.put(
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
@ticketLogPullController.get(
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
        result = await run_in_threadpool(TicketLogPullService.get_log_pull_content_services, query_db, record_id, query)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="日志拉取记录不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pulls/{record_id}/content/stream",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def stream_ticket_log_pull_content(
    request: Request,
    record_id: int,
    query: TicketLogPullContentQueryModel = Depends(TicketLogPullContentQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    流式获取日志拉取记录文本内容接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param query: 查看日志范围参数，支持开始/结束时间或时间点前后范围
    :param query_db: 数据库会话
    :return: NDJSON 事件流，包含 meta/chunk/done/error
    """
    del request
    return StreamingResponse(
        TicketLogPullService.iter_log_pull_content_stream(query_db, record_id, query),
        media_type="application/x-ndjson; charset=utf-8",
    )


@ticketLogPullController.post(
    "/logs/prepare",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def prepare_ticket_logs(
    request: Request,
    prepare_object: TicketLogPrepareRequestModel,
    query_db: Session = Depends(get_db),
):
    """
    准备工单日志查看目录接口。
    :param request: 请求对象
    :param prepare_object: 工单日志准备请求
    :param query_db: 数据库会话
    :return: 日志准备结果
    """
    try:
        result = await run_in_threadpool(
            LogService.prepare, query_db, prepare_object.ticket_id, prepare_object.record_id
        )
        return ResponseUtil.success(data=result) if result.prepared else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/logs/files",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_files(request: Request, ticket_id: int, record_id: int | None = None):
    """
    查询工单已准备日志文件列表接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :return: 日志文件列表
    """
    try:
        result = await run_in_threadpool(LogService.files, ticket_id, record_id)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
    "/logs/search",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def search_ticket_logs(
    request: Request,
    search_object: TicketLogSearchRequestModel,
    query_db: Session = Depends(get_db),
):
    """
    搜索工单日志接口。
    :param request: 请求对象
    :param search_object: 日志搜索请求
    :param query_db: 数据库会话，用于读取日志搜索资源保护配置
    :return: 搜索命中列表
    """
    try:
        result = await run_in_threadpool(
            LogService.search_keywords,
            search_object.ticket_id,
            search_object.keywords,
            search_object.search_mode,
            search_object.context_before,
            search_object.context_after,
            search_object.limit,
            search_object.with_context,
            search_object.record_id,
            search_object.file,
            query_db,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/logs/context",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_context(
    request: Request,
    ticket_id: int,
    file: str,
    line: int,
    before: int = 20,
    after: int = 20,
    record_id: int | None = None,
):
    """
    获取日志命中上下文接口。
    :param request: 请求对象
    :param ticket_id: 工单ID
    :param file: 相对日志文件路径
    :param line: 中心行号
    :param before: 前置行数
    :param after: 后置行数
    :return: 上下文内容
    """
    try:
        result = await run_in_threadpool(LogService.context, ticket_id, file, line, before, after, record_id)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
    "/logs/search_time",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def search_ticket_logs_by_time(
    request: Request,
    search_object: TicketLogSearchTimeRequestModel,
    query_db: Session = Depends(get_db),
):
    """
    按时间关键字搜索工单日志接口。
    :param request: 请求对象
    :param search_object: 日志时间搜索请求
    :param query_db: 数据库会话，用于读取日志搜索资源保护配置
    :return: 搜索命中列表
    """
    try:
        result = await run_in_threadpool(
            LogService.search_time,
            search_object.ticket_id,
            search_object.time,
            search_object.context_before,
            search_object.context_after,
            search_object.limit,
            search_object.with_context,
            search_object.record_id,
            query_db,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
    "/logs/errors",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_errors(
    request: Request,
    errors_object: TicketLogErrorsRequestModel,
    query_db: Session = Depends(get_db),
):
    """
    提取工单日志异常摘要接口。
    :param request: 请求对象
    :param errors_object: 异常摘要请求
    :param query_db: 数据库会话，用于读取日志搜索资源保护配置
    :return: 异常摘要
    """
    try:
        result = await run_in_threadpool(
            LogService.errors, errors_object.ticket_id, errors_object.limit, errors_object.record_id, query_db
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pull/store-config/template",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def download_ticket_log_pull_store_config_template(request: Request):
    """
    下载门店配置导入模板接口。
    :param request: 请求对象
    :return: 门店配置导入模板 Excel 文件
    """
    try:
        filename = "门店配置导入模板.xlsx"
        return Response(
            content=TicketLogPullService.build_store_config_import_template(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "download-filename": quote(filename),
            },
        )
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pull/store-configs",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_store_configs(
    request: Request,
    query: TicketLogPullStoreConfigQueryModel = Depends(TicketLogPullStoreConfigQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    查询门店配置列表接口。
    :param request: 请求对象
    :param query: 查询条件，支持集团编号、商户编号、机构编号、SAP机构编号和关键字搜索
    :param query_db: 数据库会话
    :return: 门店配置分页列表
    """
    try:
        return ResponseUtil.success(data=TicketLogPullService.get_store_config_list_services(query_db, query))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
    "/log-pull/store-configs/import",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:config"))],
)
@log_decorator(title="门店配置导入", business_type=1)
def import_ticket_log_pull_store_configs(
    request: Request,
    file: UploadFile = File(...),
    import_mode: str = Form(default="incremental"),
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    导入门店配置接口。
    :param request: 请求对象
    :param file: 门店配置 Excel 文件
    :param import_mode: 导入方式，incremental 为增量，overwrite 为覆盖
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 导入汇总结果
    """
    try:
        if not file.filename.lower().endswith(".xlsx"):
            return ResponseUtil.failure(msg="仅支持 xlsx 文件")
        result = TicketLogPullService.import_store_config_services(
            query_db, file.file.read(), import_mode, current_user
        )
        return (
            ResponseUtil.success(data=result.result, msg=result.message)
            if result.is_success
            else ResponseUtil.failure(msg=result.message)
        )
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pull/project-vendor-maps",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_project_vendor_maps(
    request: Request,
    query: TicketLogPullProjectVendorMapQueryModel = Depends(TicketLogPullProjectVendorMapQueryModel.as_query),
    query_db: Session = Depends(get_db),
):
    """
    查询项目商家映射列表接口。
    :param request: 请求对象
    :param query: 查询条件，支持项目ID和关键字搜索
    :param query_db: 数据库会话
    :return: 项目商家映射列表
    """
    try:
        return ResponseUtil.success(data=TicketLogPullService.get_project_vendor_map_list_services(query_db, query))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pull/project-vendor-maps/options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_project_vendor_map_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取全部项目商家映射选项接口。
    :param request: 请求对象
    :param query_db: 数据库会话
    :return: 项目商家映射选项列表
    """
    try:
        return ResponseUtil.success(data=TicketLogPullService.get_project_vendor_map_options_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
    "/log-pull/project-vendor-maps/{project_id:int}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def get_ticket_log_pull_project_vendor_map_by_project(
    request: Request,
    project_id: int,
    query_db: Session = Depends(get_db),
):
    """
    根据项目ID获取项目商家映射接口。
    :param request: 请求对象
    :param project_id: 项目ID
    :param query_db: 数据库会话
    :return: 映射信息
    """
    try:
        result = TicketLogPullService.get_project_vendor_map_by_project_services(query_db, project_id)
        return ResponseUtil.success(data=result) if result else ResponseUtil.failure(msg="映射不存在")
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
    "/log-pull/project-vendor-maps",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:config"))],
)
@log_decorator(title="项目商家映射", business_type=1)
async def save_ticket_log_pull_project_vendor_map(
    request: Request,
    config_object: TicketLogPullProjectVendorMapUpsertModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存项目商家映射接口。
    :param request: 请求对象
    :param config_object: 项目ID、项目名称和商户编号
    :param query_db: 数据库会话
    :param current_user: 当前登录用户
    :return: 保存结果
    """
    try:
        result = TicketLogPullService.save_project_vendor_map_services(query_db, config_object, current_user)
        return (
            ResponseUtil.success(data=result.result, msg=result.message)
            if result.is_success
            else ResponseUtil.failure(msg=result.message)
        )
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

@ticketLogPullController.get(
    "/log-pulls/{record_id}/download",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:query"))],
)
async def download_ticket_log_pull(
    request: Request,
    record_id: int,
    source: str = "auto",
    query_db: Session = Depends(get_db),
):
    """
    下载日志拉取压缩包接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param source: 下载来源，auto/service/original
    :param query_db: 数据库会话
    :return: 压缩包文件
    """
    temp_file_path = None
    try:
        temp_file_path, should_cleanup, download_file_name = await run_in_threadpool(
            TicketLogPullService.download_log_pull_file_services,
            query_db,
            record_id,
            source,
        )
        if not temp_file_path:
            return ResponseUtil.failure(msg="日志拉取记录不存在或没有可下载的文件")
        background = BackgroundTask(temp_file_path.unlink, missing_ok=True) if should_cleanup else None
        return FileResponse(
            path=str(temp_file_path),
            filename=download_file_name or temp_file_path.name,
            background=background,
        )
    except Exception as e:
        logger.exception(e)
        if temp_file_path and getattr(temp_file_path, "exists", lambda: False)():
            try:
                temp_file_path.unlink(missing_ok=True)
            except Exception:
                pass
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
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
        result = await run_in_threadpool(TicketLogPullService.list_log_pull_records_services, query_db, query)
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.get(
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
        result = await run_in_threadpool(
            TicketLogPullService.list_log_pull_management_records_services,
            query_db,
            query,
        )
        if query.is_page:
            return ResponseUtil.success(model_content=result)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
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
        result = await run_in_threadpool(
            TicketLogPullService.create_log_pull_services, query_db, ticket_id, create_object, current_user
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
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
        result = await run_in_threadpool(
            TicketLogPullService.retry_log_pull_services,
            query_db,
            record_id,
            current_user,
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
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
        result = await run_in_threadpool(
            TicketLogPullService.redownload_log_pull_services, query_db, record_id, current_user
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.post(
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
        result = await run_in_threadpool(
            TicketLogPullService.reextract_log_pull_services, query_db, record_id, query, current_user
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketLogPullController.delete(
    "/log-pulls/{record_id}",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:logpull:remove"))],
)
@log_decorator(title="日志拉取记录", business_type=3)
async def delete_ticket_log_pull(
    request: Request,
    record_id: int,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    删除日志拉取记录接口。
    :param request: 请求对象
    :param record_id: 日志拉取记录ID
    :param query_db: 数据库会话
    :param current_user: 当前登录用户，用于写入审计信息
    :return: 删除结果
    """
    try:
        result = await run_in_threadpool(
            TicketLogPullService.delete_log_pull_services,
            query_db,
            record_id,
            current_user,
        )
        return ResponseUtil.success(data=result) if result.is_success else ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))
@ticketLogPullController.post(
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

