"""工单自定义实时统计的查询编排、规则聚合与通知执行服务。"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from modules.ticket.dao.ticket_custom_statistics_dao import TicketCustomStatisticsDao
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.service.stats.ticket_custom_statistics_definition_service import (
    TicketCustomStatisticsDefinitionService,
)
from modules.ticket.service.stats.ticket_statistics_notification_service import TicketStatisticsNotificationService
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.util.ticket_statistic_condition_util import match_conditions
from utils.log_util import logger


@dataclass(frozen=True)
class TicketCustomStatisticsGroup:
    """统计结果中的一个分组。"""

    code: str
    label: str
    count: int


@dataclass(frozen=True)
class TicketCustomStatisticsTicket:
    """通知中允许输出的轻量工单明细。"""

    ticket_no: str
    title: str
    ticket_url: str


@dataclass(frozen=True)
class TicketCustomStatisticsResult:
    """一次统计方案执行的内存结果。"""

    profile_code: str
    profile_label: str
    time_field: str
    time_field_label: str
    start_time: str
    end_time: str
    total_count: int
    unmatched_count: int
    groups: list[TicketCustomStatisticsGroup]
    top_tickets: list[TicketCustomStatisticsTicket]
    executed_at: str

    def to_response(self) -> dict[str, Any]:
        """在 API 与通知边界转换为 camelCase 数据。"""
        return {
            "profileCode": self.profile_code,
            "profileLabel": self.profile_label,
            "timeField": self.time_field,
            "timeFieldLabel": self.time_field_label,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "totalCount": self.total_count,
            "unmatchedCount": self.unmatched_count,
            "groups": [
                {"code": group.code, "label": group.label, "count": group.count}
                for group in self.groups
            ],
            "topTickets": [
                {"ticketNo": ticket.ticket_no, "title": ticket.title, "ticketUrl": ticket.ticket_url}
                for ticket in self.top_tickets
            ],
            "executedAt": self.executed_at,
        }


class TicketCustomStatisticsService:
    """执行不落库的、方案驱动的当前系统工单统计。"""

    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
    MAX_TICKETS_PER_PROFILE = 50_000

    @classmethod
    def run_profiles(
        cls,
        db: Session,
        *,
        trigger_source: str,
        profile_codes: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        send: bool = True,
    ) -> list[dict[str, Any]]:
        """读取配置并执行指定方案；未指定时执行全部启用方案。"""
        config = TicketSyncConfigService.load_sync_config(db)
        configured_profiles = config.get("customStatisticsProfiles")
        profiles = configured_profiles if isinstance(configured_profiles, list) else []
        selected_codes = {str(code).strip() for code in profile_codes or [] if str(code).strip()}
        available_codes = {str(profile.get("profileCode") or "") for profile in profiles}
        missing_codes = selected_codes - available_codes
        if missing_codes:
            raise ValueError(f"统计方案不存在: {', '.join(sorted(missing_codes))}")

        selected_profiles = [
            profile
            for profile in profiles
            if bool(profile.get("enabled")) and (not selected_codes or profile.get("profileCode") in selected_codes)
        ]
        if not selected_profiles:
            raise ValueError("没有可执行的启用统计方案")

        executions: list[dict[str, Any]] = []
        for profile in selected_profiles:
            result = cls.run_profile(
                db,
                profile=profile,
                start_time=start_time,
                end_time=end_time,
            )
            response = result.to_response()
            notification = cls.resolve_notification_config(profile["notification"], config.get("feishuAuth"))
            if send and notification.get("enabled"):
                response["notification"] = TicketStatisticsNotificationService.send_result(
                    db,
                    notification=notification,
                    result=response,
                )
            else:
                response["notification"] = {
                    "skipped": True,
                    "skipReason": "本次执行未发送通知" if not send else "统计方案通知未启用",
                }
            logger.info(
                f"自定义工单统计执行完成: trigger={trigger_source}, profile={result.profile_code}, "
                f"total={result.total_count}, groups={len(result.groups)}, send={send}"
            )
            executions.append(response)
        return executions

    @staticmethod
    def resolve_notification_config(
        notification: dict[str, Any],
        feishu_auth: Any,
    ) -> dict[str, Any]:
        """合并方案通知配置与同步页统一飞书凭证，方案显式值优先。"""
        resolved = dict(notification)
        common_auth = feishu_auth if isinstance(feishu_auth, dict) else {}
        if not str(resolved.get("appId") or "").strip():
            resolved["appId"] = str(common_auth.get("appId") or "").strip()
        if not str(resolved.get("appSecret") or "").strip():
            resolved["appSecret"] = str(common_auth.get("appSecret") or "").strip()
        return resolved

    @classmethod
    def run_profile(
        cls,
        db: Session,
        *,
        profile: dict[str, Any],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> TicketCustomStatisticsResult:
        """按一条统计方案查询当前工单并在内存中聚合。"""
        resolved_start, resolved_end = cls.resolve_time_range(
            profile["timeRange"],
            start_time=start_time,
            end_time=end_time,
        )
        tickets = TicketCustomStatisticsDao.list_tickets(
            db,
            time_field=profile["timeField"],
            start_time=resolved_start,
            end_time=resolved_end,
            scope=profile["scope"],
        )
        return cls.aggregate_tickets(
            profile=profile,
            tickets=tickets,
            start_time=resolved_start,
            end_time=resolved_end,
        )

    @classmethod
    def aggregate_tickets(
        cls,
        *,
        profile: dict[str, Any],
        tickets: Iterable[Ticket],
        start_time: datetime,
        end_time: datetime,
    ) -> TicketCustomStatisticsResult:
        """以白名单字段和规则配置聚合工单，不保留完整统计明细。"""
        counts: dict[tuple[str, str], int] = defaultdict(int)
        total_count = 0
        unmatched_count = 0
        top_tickets: list[TicketCustomStatisticsTicket] = []
        grouping = profile["grouping"]
        top_ticket_limit = int(profile["notification"].get("topTicketLimit") or 10)
        include_top_tickets = bool(profile["notification"].get("includeTopTickets"))
        for ticket in tickets:
            total_count += 1
            if total_count > cls.MAX_TICKETS_PER_PROFILE:
                raise ValueError(f"统计范围工单超过 {cls.MAX_TICKETS_PER_PROFILE} 条，请缩小时间范围或筛选条件")
            matches = cls.resolve_ticket_groups(ticket, grouping)
            if not matches:
                unmatched_count += 1
                if grouping.get("includeUnmatched"):
                    matches = [("unmatched", "未归类")]
            for group_code, group_label in matches:
                counts[(group_code, group_label)] += 1
            if include_top_tickets and len(top_tickets) < top_ticket_limit:
                top_tickets.append(
                    TicketCustomStatisticsTicket(
                        ticket_no=str(getattr(ticket, "ticket_no", "") or "-"),
                        title=str(getattr(ticket, "title", "") or "-"),
                        ticket_url=str(getattr(ticket, "ticket_url", "") or ""),
                    )
                )
        groups = [
            TicketCustomStatisticsGroup(code=code, label=label, count=count)
            for (code, label), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][1]))
        ]
        time_field = profile["timeField"]
        return TicketCustomStatisticsResult(
            profile_code=profile["profileCode"],
            profile_label=profile["label"],
            time_field=time_field,
            time_field_label=TicketCustomStatisticsDefinitionService.TIME_FIELD_REGISTRY[time_field],
            start_time=cls.format_time(start_time),
            end_time=cls.format_time(end_time),
            total_count=total_count,
            unmatched_count=unmatched_count,
            groups=groups,
            top_tickets=top_tickets,
            executed_at=cls.format_time(datetime.now(cls.SHANGHAI_TZ).replace(tzinfo=None)),
        )

    @classmethod
    def resolve_ticket_groups(cls, ticket: Ticket, grouping: dict[str, Any]) -> list[tuple[str, str]]:
        """根据字段分组或规则分组计算一张工单的归属。"""
        if grouping.get("mode") != "rules":
            field = grouping["sourceField"]
            value = TicketCustomStatisticsDefinitionService.build_ticket_source(ticket).get(field)
            label = str(value).strip() if value not in (None, "") else "未填写"
            return [(label, label)]

        source = TicketCustomStatisticsDefinitionService.build_ticket_source(ticket)
        matched_groups = [
            group
            for group in grouping.get("groups", [])
            if match_conditions(source, group.get("conditions"), group.get("conditionMode", "all"))
        ]
        if grouping.get("overlapMode") == "exclusive" and matched_groups:
            matched_groups = [max(matched_groups, key=lambda group: int(group.get("priority") or 0))]
        return [
            (str(group["groupCode"]), str(group.get("label") or group["groupCode"]))
            for group in matched_groups
        ]

    @classmethod
    def resolve_time_range(
        cls,
        time_range: dict[str, Any],
        *,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> tuple[datetime, datetime]:
        """将方案相对时间范围或手动覆盖转换为上海时区的数据库时间。"""
        if start_time or end_time:
            resolved_start = cls.to_shanghai_naive(start_time) if start_time else None
            resolved_end = cls.to_shanghai_naive(end_time) if end_time else None
            if not resolved_start or not resolved_end:
                raise ValueError("手动执行时 startTime 和 endTime 必须同时传入")
            if resolved_start >= resolved_end:
                raise ValueError("startTime 必须早于 endTime")
            return resolved_start, resolved_end

        now = datetime.now(cls.SHANGHAI_TZ)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        mode = time_range.get("mode")
        if mode == "yesterday":
            resolved_start, resolved_end = today_start - timedelta(days=1), today_start
        elif mode == "rolling_days":
            resolved_start, resolved_end = now - timedelta(days=int(time_range.get("rollingDays") or 1)), now
        elif mode == "current_week":
            resolved_start, resolved_end = today_start - timedelta(days=today_start.weekday()), now
        elif mode == "previous_week":
            resolved_end = today_start - timedelta(days=today_start.weekday())
            resolved_start = resolved_end - timedelta(days=7)
        elif mode == "custom":
            resolved_start = cls.parse_config_datetime(time_range.get("startTime"))
            resolved_end = cls.parse_config_datetime(time_range.get("endTime"))
            if not resolved_start or not resolved_end or resolved_start >= resolved_end:
                raise ValueError("自定义时间范围必须配置有效的开始时间和结束时间")
            return resolved_start, resolved_end
        else:
            resolved_start, resolved_end = today_start, now
        return resolved_start.replace(tzinfo=None), resolved_end.replace(tzinfo=None)

    @classmethod
    def parse_config_datetime(cls, value: Any) -> datetime | None:
        """解析配置中的 ISO 日期时间，并归一化为上海本地无时区时间。"""
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return cls.to_shanghai_naive(datetime.fromisoformat(text.replace("Z", "+00:00")))
        except ValueError:
            return None

    @classmethod
    def to_shanghai_naive(cls, value: datetime) -> datetime:
        """将前端传入的有时区或无时区时间转换为数据库使用的上海本地时间。"""
        if value.tzinfo is None:
            return value
        return value.astimezone(cls.SHANGHAI_TZ).replace(tzinfo=None)

    @staticmethod
    def format_time(value: datetime) -> str:
        """格式化通知和接口使用的时间文本。"""
        return value.strftime("%Y-%m-%d %H:%M:%S")
