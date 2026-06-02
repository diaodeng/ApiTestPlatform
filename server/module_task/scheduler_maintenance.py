import asyncio
from typing import Any

from config.database import SessionLocal
from module_hrm.entity.vo.report_vo import ReportDelModel
from module_hrm.service.report_service import ReportService
from module_task.runtime_control import TaskStopRequestedError, is_task_stop_requested
from modules.ticket.service.ticket_sync_service import TicketSyncService
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
        "远端工单拉取任务执行完成 | consumer={}, pulled={}, synced={}, failed={}, acked={}",
        result.get("consumer"),
        result.get("pulledCount"),
        result.get("syncedCount"),
        result.get("failedCount"),
        result.get("ackedCount"),
    )
    return result
