import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.orm import Session

from config.get_db import get_db
from context.request_context import get_current_trace_id
from module_admin.aspect.interface_auth import CheckUserInterfaceAuth
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_admin.service.login_service import LoginService
from modules.ticket.entity.vo.ticket_vo import (
    TicketBatchReclassifyRequestModel,
    TicketExternalSyncUpsertModel,
    TicketSyncAckRequestModel,
    TicketSyncGroupPushSendModel,
    TicketSyncPersonReminderPreviewModel,
    TicketSyncPersonReminderRunModel,
    TicketSyncPullQueryModel,
    TicketSyncSummaryRunModel,
)
from modules.ticket.service.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.ticket_sync_group_push_service import TicketSyncGroupPushService
from modules.ticket.service.ticket_sync_service import TicketSyncService
from utils.log_util import logger
from utils.response_util import ResponseUtil

ticketSyncController = APIRouter(prefix="/ticket", dependencies=[Depends(LoginService.get_current_user)])

@ticketSyncController.post("/sync/external", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:external"))])
async def sync_external_ticket(
    request: Request,
    background_tasks: BackgroundTasks,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    外部工单系统同步数据入库接口。

    兼容 JSON 和 `multipart/form-data` / `application/x-www-form-urlencoded` 提交。
    表单模式下支持扁平字段，会自动归一化为 `TicketExternalSyncUpsertModel`。
    必填字段：`ticketNo`、`description`、`internalPriority`、`ticketVender`、`ticketModle`、`createTime`、`reporterName`。
    可选门店字段：`ticketStore` / `storeInfo` / `storeId`（用于匹配门店配置并支持消息模板变量）。
    可选链接字段：`url` / `ticketUrl` / `detailUrl`（将写入 `ticket_url` 供页面跳转和消息模板使用）。
    `title` 可选，缺省时由服务层按“轻量AI总结 -> 描述前100字符”规则补齐。
    为避免长时间阻塞主请求，AI翻译、AI标题总结、自动化和群推送改为入库成功后后台异步执行。
    若 Celery Worker 可用，优先投递 Celery 任务；否则回退 FastAPI 本地后台任务。
    """
    try:
        payload = await TicketSyncService.load_external_sync_payload(request)
        sync_config = await run_in_threadpool(TicketSyncConfigService.load_sync_config, query_db)
        external_sync_required_fields = (
            sync_config.get("externalSyncRequiredFields")
            if isinstance(sync_config, dict)
            else None
        )
        payload = TicketSyncService.normalize_external_sync_payload(payload, external_sync_required_fields)
        sync_object = TicketExternalSyncUpsertModel.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            f"外部工单同步模型校验失败: {exc.errors()}; payload="
            f"{json.dumps(payload, ensure_ascii=False) if 'payload' in locals() else ''}"
        )
        raise HTTPException(
            status_code=422,
            detail={
                "message": "外部工单同步模型校验失败",
                "errors": exc.errors(),
            },
        ) from exc
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        trace_id = get_current_trace_id()
        result = await run_in_threadpool(
            TicketSyncService.sync_external_ticket,
            query_db,
            sync_object,
            current_user,
            "external_sync",
            True,
        )
        if result.is_success:
            deferred_dispatch = await run_in_threadpool(
                TicketSyncService.dispatch_deferred_sync_post_process_task,
                sync_object.model_dump(),
                current_user.model_dump(),
                "external_sync",
                trace_id,
            )
            if deferred_dispatch.get("mode") != TicketSyncService.CELERY_DISPATCH_MODE:
                background_tasks.add_task(
                    TicketSyncService.run_deferred_sync_post_process,
                    sync_object.model_dump(),
                    current_user.model_dump(),
                    "external_sync",
                    trace_id,
                )

            result_data = dict(result.result or {}) if isinstance(result.result, dict) else {"rawResult": result.result}
            result_data["deferredDispatch"] = deferred_dispatch
            return ResponseUtil.success(data=result_data, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.get("/sync/pending", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:pull"))])
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
        result = await run_in_threadpool(TicketSyncService.pull_pending_tickets, query_db, query, current_user)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post("/sync/ack", dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:pull"))])
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
        result = await run_in_threadpool(TicketSyncService.ack_sync_delivery, query_db, ack_object, current_user)
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.get(
    "/sync/automation",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:list"))],
)
async def get_sync_automation_config(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单同步自动化配置。
    """
    try:
        return ResponseUtil.success(data=TicketSyncConfigService.get_sync_automation_config_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.put(
    "/sync/automation",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:edit"))],
)
async def update_sync_automation_config(
    request: Request,
    config_value: dict,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    保存工单同步自动化配置。
    """
    try:
        result = TicketSyncConfigService.update_sync_automation_config_services(
            query_db,
            config_value,
            current_user.user.user_name,
        )
        if result.is_success:
            return ResponseUtil.success(data=result.result, msg=result.message)
        return ResponseUtil.failure(msg=result.message)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/automation/bitable-pull/fields-preview",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:list"))],
)
async def preview_bitable_pull_fields(
    request: Request,
    config_value: dict,
    query_db: Session = Depends(get_db),
):
    """
    根据当前主动拉取配置预览多维表格字段列表。
    """
    try:
        result = await run_in_threadpool(
            TicketSyncService.preview_bitable_pull_fields_services,
            query_db,
            bitable_pull_override=config_value,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.get(
    "/sync/notify/push-options",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:list"))],
)
async def get_sync_notify_push_options(request: Request, query_db: Session = Depends(get_db)):
    """
    获取工单通知可用推送配置选项。
    :param request: 请求对象。
    :param query_db: 数据库会话。
    :return: 推送配置列表。
    """
    try:
        return ResponseUtil.success(data=TicketSyncConfigService.get_sync_notify_push_options_services(query_db))
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/notify/person/preview",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:list"))],
)
async def preview_sync_person_reminder(
    request: Request,
    query_object: TicketSyncPersonReminderPreviewModel,
    query_db: Session = Depends(get_db),
):
    """
    按用户ID或邮箱预览工单催办统计。
    :param request: 请求对象。
    :param query_object: 预览参数，支持 userId 或 email。
    :param query_db: 数据库会话。
    :return: 人维度超时统计结果。
    """
    try:
        result = TicketSyncService.preview_person_reminder_services(
            query_db,
            user_id=query_object.user_id,
            email=query_object.email,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/notify/person/run",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:edit"))],
)
async def run_sync_person_reminder(
    request: Request,
    query_object: TicketSyncPersonReminderRunModel,
    query_db: Session = Depends(get_db),
):
    """
    手动执行工单人维度催办通知。
    :param request: 请求对象。
    :param query_object: 执行参数，支持限定 userId 或 email。
    :param query_db: 数据库会话。
    :return: 执行结果摘要。
    """
    try:
        result = TicketSyncService.run_person_reminder_services(
            query_db,
            trigger_source="manual",
            user_id=query_object.user_id,
            email=query_object.email,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/notify/summary/run",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:edit"))],
)
async def run_sync_summary_report(
    request: Request,
    query_object: TicketSyncSummaryRunModel,
    query_db: Session = Depends(get_db),
):
    """
    手动执行工单汇总统计通知。
    :param request: 请求对象。
    :param query_object: 汇总统计执行参数，支持可选起止时间。
    :param query_db: 数据库会话。
    :return: 执行结果摘要。
    """
    try:
        result = TicketSyncService.run_summary_report_services(
            query_db,
            trigger_source="manual",
            start_time=query_object.start_time,
            end_time=query_object.end_time,
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/notify/group/send-by-ticket",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:edit"))],
)
async def send_sync_group_push_by_ticket(
    request: Request,
    query_object: TicketSyncGroupPushSendModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    按工单号手动发送群消息通知。
    :param request: 请求对象。
    :param query_object: 发送参数，包含工单号、可选推送渠道和模板、是否强制推送。
    :param query_db: 数据库会话。
    :param current_user: 当前登录用户，用于写入推送状态更新人。
    :return: 推送执行结果。
    """
    logger.info(f"/sync/notify/group/send-by-ticket 请求参数： {query_object.model_dump_json()}")
    try:
        result = TicketSyncGroupPushService.send_group_push_by_ticket_no_services(
            query_db,
            ticket_no=query_object.ticket_no,
            push_ids=query_object.push_ids,
            message_template=query_object.message_template,
            force_push=query_object.force_push,
            update_by=str(current_user.user.user_name or "system"),
        )
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.post(
    "/sync/auto-category/reclassify",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:edit"))],
)
def batch_reclassify_sync_tickets(
    request: Request,
    query_object: TicketBatchReclassifyRequestModel,
    query_db: Session = Depends(get_db),
    current_user: CurrentUserModel = Depends(LoginService.get_current_user),
):
    """
    批量重跑工单自动分类。
    :param request: 请求对象。
    :param query_object: 批量重归类参数，支持指定 ticketNos（ticketNo 列表）或按分页扫描。
    :param query_db: 数据库会话。
    :param current_user: 当前登录用户。
    :return: 批量重归类执行结果。
    """
    logger.info(
        f"/sync/auto-category/reclassify 请求参数: {query_object.model_dump_json()}, "
        f"user={current_user.user.user_name if current_user and current_user.user else 'system'}"
    )
    try:
        result = TicketSyncService.batch_reclassify_ticket_categories_services(query_db, query_object, current_user)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))


@ticketSyncController.get(
    "/sync/auto-category/stats",
    dependencies=[Depends(CheckUserInterfaceAuth("ticket:sync:config:list"))],
)
async def get_sync_auto_category_stats(
    request: Request,
    query_db: Session = Depends(get_db),
):
    """
    获取工单自动归类统计摘要。
    :param request: 请求对象。
    :param query_db: 数据库会话。
    :return: 未归类统计结果。
    """
    logger.info("/sync/auto-category/stats 请求到达: 仅统计未归类数量，不执行自动归类")
    try:
        result = TicketSyncService.get_uncategorized_ticket_statistics_services(query_db)
        return ResponseUtil.success(data=result)
    except Exception as e:
        logger.exception(e)
        return ResponseUtil.error(msg=str(e))

