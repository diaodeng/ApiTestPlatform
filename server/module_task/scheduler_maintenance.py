import asyncio
import json
from typing import Any

from config.database import SessionLocal
from module_hrm.entity.vo.report_vo import ReportDelModel
from module_hrm.service.report_service import ReportService
from module_task.runtime_control import TaskStopRequestedError, is_task_stop_requested
from modules.ticket.service.ticket_sync_service import TicketSyncService
from modules.ticket.service.ticket_topic_stats_service import TicketTopicStatsService
from utils.log_util import logger

from .task_register import register_job


def _build_remote_sync_override(
    *,
    consumer: str | None = None,
    limit: int | None = None,
    include_closed: bool | None = None,
    pull_url: str | None = None,
    ack_url: str | None = None,
    source_system: str | None = None,
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    组装远端工单同步覆盖配置。

    :param consumer: 同步消费者。
    :param limit: 拉取上限。
    :param include_closed: 是否包含关闭工单。
    :param pull_url: 拉取地址。
    :param ack_url: 回写地址。
    :param source_system: 远端系统标识。
    :param headers: 额外请求头。
    :return: 覆盖配置字典。
    """
    override: dict[str, Any] = {}
    remote_sync: dict[str, Any] = {}
    if consumer is not None:
        remote_sync["consumer"] = consumer
    if limit is not None:
        remote_sync["limit"] = limit
    if include_closed is not None:
        remote_sync["includeClosed"] = include_closed
    if pull_url is not None:
        remote_sync["pullUrl"] = pull_url
    if ack_url is not None:
        remote_sync["ackUrl"] = ack_url
    if source_system is not None:
        remote_sync["sourceSystem"] = source_system
    if headers:
        remote_sync["headers"] = headers
    if remote_sync:
        override["remoteSync"] = remote_sync
    return override


def _build_person_reminder_config_override(kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    从定时任务参数中提取人员催办覆盖配置。

    :param kwargs: 定时任务关键字参数。
    :return: 非空覆盖配置；为空的字段由全局同步参数配置兜底。
    """
    nested_config = kwargs.pop("personReminder", None)
    if nested_config is None:
        nested_config = kwargs.pop("person_reminder", None)
    source_config = dict(nested_config) if isinstance(nested_config, dict) else {}
    for key, value in kwargs.items():
        if value is not None and str(value).strip() != "":
            source_config[key] = value
    field_aliases = {
        "appToken": ("appToken", "app_token"),
        "tableId": ("tableId", "table_id"),
        "viewId": ("viewId", "view_id", "view"),
        "filterFormula": ("filterFormula", "filter_formula", "feishuFilter", "feishu_filter", "filter"),
        "personField": ("personField", "person_field", "personFieldName", "person_field_name"),
        "timeField": ("timeField", "time_field", "timeFieldName", "time_field_name"),
        "dataSource": ("dataSource", "data_source"),
        "pageSize": ("pageSize", "page_size"),
    }
    override: dict[str, Any] = {}
    for target_key, aliases in field_aliases.items():
        for alias in aliases:
            if alias in source_config:
                value = source_config.get(alias)
                if value is not None and str(value).strip() != "":
                    override[target_key] = value
                break
    return override


def _build_bitable_pull_config_override(kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    从定时任务参数中提取飞书多维表格主动拉取覆盖配置。

    :param kwargs: 定时任务关键字参数。
    :return: 非空覆盖配置。
    """
    nested_config = kwargs.pop("bitablePull", None)
    if nested_config is None:
        nested_config = kwargs.pop("bitable_pull", None)
    source_config = dict(nested_config) if isinstance(nested_config, dict) else {}
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, str) and str(value).strip() == "":
            continue
        source_config[key] = value
    field_aliases = {
        "enabled": ("enabled",),
        "appId": ("appId", "app_id"),
        "appSecret": ("appSecret", "app_secret"),
        "appToken": ("appToken", "app_token"),
        "tableId": ("tableId", "table_id"),
        "viewId": ("viewId", "view_id", "view"),
        "pageSize": ("pageSize", "page_size"),
        "filterFormula": ("filterFormula", "filter_formula", "filter"),
        "sourceSystem": ("sourceSystem", "source_system"),
        "ticketNoField": ("ticketNoField", "ticket_no_field"),
        "updatedAtField": ("updatedAtField", "updated_at_field"),
        "sortField": ("sortField", "sort_field"),
        "includeRecordUrl": ("includeRecordUrl", "include_record_url"),
        "createdAfter": ("createdAfter", "created_after", "startTime", "start_time", "beginTime", "begin_time"),
        "fieldMappings": ("fieldMappings", "field_mappings"),
        "automation": ("automation",),
    }
    override: dict[str, Any] = {}
    for target_key, aliases in field_aliases.items():
        for alias in aliases:
            if alias in source_config:
                override[target_key] = source_config.get(alias)
                break
    return override


@register_job("module_task.scheduler_maintenance.cleanup_test_reports")
def cleanup_test_reports(
    *args,
    report_ids: list[int | str] | None = None,
    begin_time=None,
    end_time=None,
    user_id: int | None = None,
    **kwargs,
):
    """
    清理测试报告定时任务。

    :param report_ids: 报告ID列表，优先按ID清理。
    :param begin_time: 开始时间。
    :param end_time: 结束时间。
    :param user_id: 用户ID，选填后仅清理该用户对应报告。
    :return: 清理结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")
    cleanup_model = ReportDelModel.model_validate(
        {
            "reportIds": report_ids or kwargs.pop("reportIds", None) or kwargs.pop("report_ids", None) or [],
            "beginTime": begin_time if begin_time is not None else kwargs.pop("beginTime", None),
            "endTime": end_time if end_time is not None else kwargs.pop("endTime", None),
            "userId": user_id if user_id is not None else kwargs.pop("userId", None),
        }
    )
    with SessionLocal() as db:
        result = asyncio.run(ReportService.delete_reports(db, cleanup_model))
    deleted_count = int((result.result or {}).get("deletedCount") or 0) if isinstance(result.result, dict) else 0
    logger.info(
        "测试报告清理任务执行完成 | deleted_count={}, report_ids={}, begin_time={}, end_time={}, user_id={}",
        deleted_count,
        cleanup_model.report_ids,
        cleanup_model.begin_time,
        cleanup_model.end_time,
        cleanup_model.user_id,
    )
    return {
        "deletedCount": deleted_count,
        "message": result.message,
    }


@register_job("module_task.scheduler_maintenance.pull_public_ticket_sync")
def pull_public_ticket_sync(
    *args,
    consumer: str | None = None,
    limit: int | None = None,
    include_closed: bool | None = None,
    pull_url: str | None = None,
    ack_url: str | None = None,
    source_system: str | None = None,
    headers: dict[str, Any] | None = None,
    **kwargs,
):
    """
    远端工单拉取定时任务。

    :param consumer: 同步消费者，未传则使用系统配置。
    :param limit: 拉取上限，未传则使用系统配置。
    :param include_closed: 是否包含关闭工单。
    :param pull_url: 拉取地址覆盖值。
    :param ack_url: 回写地址覆盖值。
    :param source_system: 远端系统标识覆盖值。
    :param headers: 请求头覆盖值。
    :return: 同步结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")
    override = _build_remote_sync_override(
        consumer=consumer if consumer is not None else kwargs.pop("consumer", None),
        limit=limit if limit is not None else kwargs.pop("limit", None),
        include_closed=include_closed if include_closed is not None else kwargs.pop("includeClosed", None),
        pull_url=pull_url if pull_url is not None else kwargs.pop("pullUrl", None),
        ack_url=ack_url if ack_url is not None else kwargs.pop("ackUrl", None),
        source_system=source_system if source_system is not None else kwargs.pop("sourceSystem", None),
        headers=headers if headers is not None else kwargs.pop("headers", None),
    )
    with SessionLocal() as db:
        result = TicketSyncService.sync_remote_pending_tickets(db, current_user=None, remote_sync_override=override)
    logger.info(
        "远端工单拉取任务执行完成 | consumer={}, pulled={}, synced={}, skipped={}, failed={}, acked={}",
        result.get("consumer"),
        result.get("pulledCount"),
        result.get("syncedCount"),
        result.get("skippedCount"),
        result.get("failedCount"),
        result.get("ackedCount"),
    )
    return result


@register_job("module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync")
def pull_feishu_bitable_ticket_sync(
    *args,
    **kwargs,
):
    """
    飞书多维表格工单主动拉取定时任务。

    :param kwargs: 支持 bitablePull 嵌套对象或平铺字段覆盖 appToken/tableId/viewId/
        filterFormula/pageSize/fieldMappings/createdAfter。
    :return: 执行结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")
    override = _build_bitable_pull_config_override(kwargs)
    with SessionLocal() as db:
        result = TicketSyncService.run_bitable_pull_services(
            db,
            trigger_source="scheduler",
            current_user=None,
            bitable_pull_override=override,
        )
    logger.info(
        f"飞书多维表格主动拉取任务执行完成 | record_count={result.get('recordCount')} "
        f"synced={result.get('syncedCount')} skipped={result.get('skippedCount')} "
        f"failed={result.get('failedCount')} override_keys={list(override.keys())}"
    )
    return result


@register_job("module_task.scheduler_maintenance.ticket_person_overdue_reminder")
def ticket_person_overdue_reminder(
    *args,
    user_id: int | None = None,
    email: str | None = None,
    **kwargs,
):
    """
    工单人维度催办定时任务。

    :param user_id: 可选用户ID，传入后仅提醒该用户。
    :param email: 可选邮箱，传入后仅提醒该邮箱对应用户。
    :param kwargs: 支持 appToken/tableId/viewId/filterFormula/personField/timeField 等任务级覆盖配置。
    :return: 执行结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")

    resolved_user_id = user_id if user_id is not None else kwargs.pop("userId", None)
    resolved_emails = email if email is not None else kwargs.pop("email", [])
    is_all_raw = kwargs.pop("isAll", False)
    is_all = (
        str(is_all_raw).strip().lower() in {"1", "true", "yes", "y", "on"}
        if isinstance(is_all_raw, str)
        else bool(is_all_raw)
    )
    person_config_override = _build_person_reminder_config_override(kwargs)
    if is_all:
        with SessionLocal() as db:
            result = TicketSyncService.run_person_reminder_services(
                db,
                trigger_source="scheduler",
                is_all=is_all,
                person_config_override=person_config_override,
            )
        logger.info(
            f"工单人维度全员催办任务执行完成 | sent_people={result.get('sentPeople')} "
            f"sent_push_count={result.get('sentPushCount')} skipped={result.get('skipped')} "
            f"override_keys={list(person_config_override.keys())}"
        )
        return result


    try:
        if resolved_emails and isinstance(resolved_emails, str):
            parsed_emails = json.loads(resolved_emails)
            resolved_emails = parsed_emails if isinstance(parsed_emails, list) else [parsed_emails]
    except Exception:
        resolved_emails = [resolved_emails]
    if not isinstance(resolved_emails, list):
        resolved_emails = [resolved_emails] if resolved_emails else []

    normalized_user_id = None
    try:
        if resolved_user_id not in (None, ""):
            normalized_user_id = int(resolved_user_id)
    except Exception:
        normalized_user_id = None
    if normalized_user_id and not resolved_emails:
        resolved_emails = [None]
    result = {"skipped": True, "skipReason": "未指定用户或邮箱"}
    for resolved_email in resolved_emails:
        with SessionLocal() as db:
            result = TicketSyncService.run_person_reminder_services(
                db,
                trigger_source="scheduler",
                user_id=normalized_user_id,
                email=str(resolved_email or "").strip() or None,
                person_config_override=person_config_override,
            )
        logger.info(
            f"工单人维度催办任务执行完成 | user_id={resolved_user_id or '-'} "
            f"email={resolved_email or '-'} sent_people={result.get('sentPeople')} "
            f"sent_push_count={result.get('sentPushCount')} skipped={result.get('skipped')} "
            f"override_keys={list(person_config_override.keys())}"
        )
    return result


@register_job("module_task.scheduler_maintenance.ticket_summary_report")
def ticket_summary_report(
    *args,
    start_time: str | None = None,
    end_time: str | None = None,
    **kwargs,
):
    """
    工单汇总统计通知定时任务。

    :param start_time: 可选统计开始时间，支持日期时间字符串。
    :param end_time: 可选统计结束时间，支持日期时间字符串。
    :return: 执行结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")

    resolved_start_time = start_time if start_time is not None else kwargs.pop("startTime", None)
    resolved_end_time = end_time if end_time is not None else kwargs.pop("endTime", None)

    with SessionLocal() as db:
        result = TicketSyncService.run_summary_report_services(
            db,
            trigger_source="scheduler",
            start_time=resolved_start_time,
            end_time=resolved_end_time,
        )
    logger.info(
        "工单汇总统计通知任务执行完成 | start_time={} end_time={} push_success={} chat_success={} skipped={}",
        resolved_start_time or "-",
        resolved_end_time or "-",
        result.get("pushSuccessCount"),
        result.get("chatSuccessCount"),
        result.get("skipped"),
    )
    return result


@register_job("module_task.scheduler_maintenance.ticket_topic_stats_report")
def ticket_topic_stats_report(
    *args,
    start_date: str | None = None,
    end_date: str | None = None,
    sources: list[dict[str, Any]] | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    receive_chat_ids: list[str] | str | None = None,
    send: bool | None = None,
    keyword: str = "TRunner",
    page_size: int | None = None,
    **kwargs,
):
    """
    专题工单会话状态统计定时任务。

    :param start_date: 统计开始日期，格式 YYYY-MM-DD；为空时取上海时区当天。
    :param end_date: 统计结束日期，格式 YYYY-MM-DD；为空时取上海时区当天。
    :param sources: 飞书群来源列表，每项包含 name、chatId/chat_id、priority。
    :param app_id: 飞书应用 app_id。
    :param app_secret: 飞书应用 app_secret。
    :param receive_chat_ids: 发送统计卡片的群 chat_id 列表；为空时默认发到 sources 中配置的群。
    :param send: 是否发送飞书卡片。
    :param keyword: 卡片副标题关键字。
    :param page_size: 单页拉取消息数量。
    :return: 统计结果摘要。
    """
    task_id = int(kwargs.pop("_task_id", 0) or 0)
    if task_id and is_task_stop_requested(task_id):
        raise TaskStopRequestedError("任务已手动终止")

    resolved_sources = sources if sources is not None else kwargs.pop("sources", None)
    resolved_start_date = start_date if start_date is not None else kwargs.pop("startDate", None)
    resolved_end_date = end_date if end_date is not None else kwargs.pop("endDate", None)
    resolved_app_id = app_id if app_id is not None else kwargs.pop("appId", None)
    resolved_app_secret = app_secret if app_secret is not None else kwargs.pop("appSecret", None)
    resolved_receive_chat_ids = receive_chat_ids if receive_chat_ids is not None else (
        kwargs.pop("receiveChatIds", None) or kwargs.pop("appChatIds", None)
    )
    resolved_send = bool(send if send is not None else kwargs.pop("send", False))
    resolved_keyword = keyword if keyword is not None else kwargs.pop("keyword", "TRunner")
    resolved_page_size = page_size if page_size is not None else kwargs.pop("pageSize", 50)

    logger.info(
        f"专题工单会话状态统计任务开始 | start_date={resolved_start_date or '-'} "
        f"end_date={resolved_end_date or '-'} source_count={len(resolved_sources or [])} "
        f"send={resolved_send} keyword={resolved_keyword or '-'}"
    )
    result = TicketTopicStatsService.run_topic_stats(
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        sources=resolved_sources,
        app_id=resolved_app_id,
        app_secret=resolved_app_secret,
        receive_chat_ids=resolved_receive_chat_ids,
        send=resolved_send,
        keyword=str(resolved_keyword or "TRunner"),
        page_size=int(resolved_page_size or 50),
    )
    logger.info(
        f"专题工单会话状态统计任务完成 | total={result['summary']['total']} "
        f"status={result['summary']['status']} category={result['summary']['category']}"
    )
    return {
        "range": result.get("range"),
        "summary": result.get("summary"),
        "sent": bool(result.get("response")),
        "response": result.get("response"),
    }
