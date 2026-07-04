from typing import Any

from sqlalchemy.orm import Session

from modules.ticket.service.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.ticket_sync_notify_service import TicketSyncNotifyService
from utils.log_util import logger


class TicketSyncNotificationJobService:
    """
    工单同步通知任务编排服务。

    该服务只负责读取同步自动化配置并编排人员催办、汇总统计等通知任务；
    具体飞书、多维表格、本地统计和推送发送逻辑仍由 TicketSyncNotifyService 承接。
    """

    @classmethod
    def preview_person_reminder_services(
        cls,
        db: Session,
        *,
        user_id: int | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """
        预览人维度催办统计。

        :param db: 数据库会话。
        :param user_id: 可选用户ID。
        :param email: 可选邮箱。
        :return: 统计结果。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        person_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "personReminder",
            TicketSyncConfigService.default_person_reminder_config(),
        )
        return TicketSyncNotifyService.preview_person_overdue_statistics(
            db,
            config=person_config,
            user_id=user_id,
            email=email,
        )

    @classmethod
    def run_person_reminder_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        user_id: int | None = None,
        email: str | None = None,
        is_all: bool = False,
        person_config_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行人维度催办通知。

        :param db: 数据库会话。
        :param trigger_source: 触发来源。
        :param user_id: 可选用户ID。
        :param email: 可选邮箱。
        :param is_all: 是否直接统计所有。
        :param person_config_override: 定时任务传入的人员催办配置覆盖项，非空字段优先于全局参数配置。
        :return: 执行结果摘要。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        person_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "personReminder",
            TicketSyncConfigService.default_person_reminder_config(),
        )
        if isinstance(person_config_override, dict):
            normalized_override = {
                str(key): value
                for key, value in person_config_override.items()
                if value is not None and str(value).strip() != ""
            }
            if normalized_override:
                person_config = {**person_config, **normalized_override}
                logger.info(
                    f"人员催办使用任务级配置覆盖: trigger={trigger_source}, "
                    f"override_keys={list(normalized_override.keys())}"
                )
        return TicketSyncNotifyService.run_person_overdue_reminder(
            db,
            config=person_config,
            trigger_source=trigger_source,
            user_id=user_id,
            email=email,
            is_all=is_all,
        )

    @classmethod
    def run_summary_report_services(
        cls,
        db: Session,
        *,
        trigger_source: str,
        start_time: Any | None = None,
        end_time: Any | None = None,
    ) -> dict[str, Any]:
        """
        执行工单汇总统计通知。

        :param db: 数据库会话。
        :param trigger_source: 触发来源，支持 manual/scheduler。
        :param start_time: 可选统计开始时间。
        :param end_time: 可选统计结束时间。
        :return: 执行结果摘要。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        summary_config = TicketSyncConfigService.resolve_bitable_runtime_config(
            config,
            "summaryReport",
            TicketSyncConfigService.default_summary_report_config(),
        )
        parsed_start_time = TicketSyncNotifyService.parse_datetime_value(start_time)
        parsed_end_time = TicketSyncNotifyService.parse_datetime_value(end_time)
        return TicketSyncNotifyService.run_ticket_summary_report(
            db,
            config=summary_config,
            trigger_source=trigger_source,
            start_time=parsed_start_time,
            end_time=parsed_end_time,
        )
