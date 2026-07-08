from datetime import datetime
from typing import TYPE_CHECKING, Any

from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus

if TYPE_CHECKING:
    from modules.ticket.entity.do.ticket_do import Ticket


class TicketProcessingMetricService:
    """
    工单处理统计时间口径服务。

    该服务只负责 submit_time、processed_at、released_at、verified_at 等统计字段的业务判定，
    不处理数据库提交、通知、AI 或外部同步副作用。
    """

    CONCLUSION_FIELDS = {
        "root_cause",
        "solution",
        "is_problem",
        "root_cause_type",
        "solution_type",
        "resolution_code",
        "problem_pattern_code",
        "problem_pattern_name",
    }
    PROCESSED_STATUSES = {
        TicketStatus.WAIT_RELEASE.value,
        TicketStatus.WAIT_VERIFY.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.CLOSED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.NON_PROBLEM.value,
        TicketStatus.DESIGN_AS_EXPECTED.value,
        TicketStatus.USER_MISOPERATION.value,
        TicketStatus.DUPLICATED.value,
    }
    PROCESSING_EVENT_TYPES = {
        TicketEventType.ANALYSIS.value,
        TicketEventType.RCA.value,
        TicketEventType.LOG_ANALYSIS.value,
        TicketEventType.DB_CHECK.value,
        TicketEventType.FIX_APPLIED.value,
        TicketEventType.DEPLOYED.value,
        TicketEventType.VERIFIED.value,
        TicketEventType.RESOLVED.value,
        TicketEventType.CLOSED.value,
    }

    @classmethod
    def parse_datetime_value(cls, value: Any) -> datetime | None:
        """
        解析日期时间输入，兼容 datetime、ISO 字符串和常见日期字符串。
        :param value: 原始时间值。
        :return: 解析后的无时区 datetime，失败返回 None。
        """
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).replace(tzinfo=None)
        except Exception:
            pass
        for pattern in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text[:19], pattern)
            except ValueError:
                continue
        return None

    @classmethod
    def resolve_submit_time(
        cls,
        *,
        explicit_submit_time: Any = None,
        extra_data: dict[str, Any] | None = None,
        create_time: Any = None,
        fallback_time: Any = None,
    ) -> datetime | None:
        """
        解析工单业务提交时间，优先显式字段，再读外部同步元数据，最后回退创建时间。
        :param explicit_submit_time: 入参或历史工单上的 submit_time。
        :param extra_data: 工单扩展字段。
        :param create_time: 工单创建时间。
        :param fallback_time: 兜底时间。
        :return: 业务提交时间。
        """
        parsed = cls.parse_datetime_value(explicit_submit_time)
        if parsed:
            return parsed
        extra = extra_data if isinstance(extra_data, dict) else {}
        external_sync = extra.get("external_sync") if isinstance(extra.get("external_sync"), dict) else {}
        source = external_sync.get("source") if isinstance(external_sync.get("source"), dict) else {}
        for candidate in (
            external_sync.get("externalCreateTime"),
            source.get("externalCreateTime"),
            extra.get("externalCreateTime"),
            extra.get("external_create_time"),
        ):
            parsed = cls.parse_datetime_value(candidate)
            if parsed:
                return parsed
        return cls.parse_datetime_value(create_time) or cls.parse_datetime_value(fallback_time)

    @classmethod
    def resolve_affected_version(
        cls,
        *,
        affected_version: Any = None,
        version_key: Any = None,
        extra_data: dict[str, Any] | None = None,
        fallback: Any = None,
    ) -> str:
        """
        解析问题发生/分析版本，兼容历史 extra_data.version_key。
        :param affected_version: 显式发生版本。
        :param version_key: 历史版本号字段。
        :param extra_data: 工单扩展字段。
        :param fallback: 旧工单字段兜底。
        :return: 版本文本。
        """
        extra = extra_data if isinstance(extra_data, dict) else {}
        for candidate in (affected_version, version_key, extra.get("version_key"), extra.get("versionKey"), fallback):
            text = str(candidate or "").strip()
            if text:
                return text
        return ""

    @classmethod
    def has_processing_conclusion(cls, payload: dict[str, Any] | None) -> bool:
        """
        判断更新载荷是否包含有效处理结论。
        :param payload: 工单更新字段。
        :return: 是否包含结论。
        """
        data = payload if isinstance(payload, dict) else {}
        for field in cls.CONCLUSION_FIELDS:
            if field not in data:
                continue
            value = data.get(field)
            if isinstance(value, bool):
                return True
            if value is not None and str(value).strip():
                return True
        return False

    @classmethod
    def apply_create_fields(cls, data: dict[str, Any], *, now: datetime) -> None:
        """
        为新增工单补齐提交时间和发生版本。
        :param data: 待入库字段字典。
        :param now: 当前时间。
        :return: 无，直接修改 data。
        """
        extra_data = data.get("extra_data") if isinstance(data.get("extra_data"), dict) else {}
        data["submit_time"] = cls.resolve_submit_time(
            explicit_submit_time=data.get("submit_time"),
            extra_data=extra_data,
            create_time=data.get("create_time") or now,
            fallback_time=now,
        )
        data["affected_version"] = cls.resolve_affected_version(
            affected_version=data.get("affected_version"),
            version_key=data.get("version_key"),
            extra_data=extra_data,
        )

    @classmethod
    def apply_update_version_fields(cls, ticket: "Ticket", data: dict[str, Any]) -> None:
        """
        编辑工单时保持 affected_version 与历史 version_key 兼容。
        :param ticket: 当前工单。
        :param data: 待更新字段字典。
        :return: 无，直接修改 data。
        """
        extra_data = data.get("extra_data") if isinstance(data.get("extra_data"), dict) else {}
        if "affected_version" in data or "extra_data" in data:
            data["affected_version"] = cls.resolve_affected_version(
                affected_version=data.get("affected_version"),
                version_key=extra_data.get("version_key"),
                extra_data=extra_data,
                fallback=getattr(ticket, "affected_version", None),
            )
        submit_time = cls.resolve_submit_time(
            explicit_submit_time=data.get("submit_time"),
            extra_data=extra_data,
            create_time=getattr(ticket, "create_time", None),
            fallback_time=getattr(ticket, "create_time", None),
        )
        if "submit_time" in data or (not getattr(ticket, "submit_time", None) and submit_time):
            data["submit_time"] = submit_time

    @classmethod
    def apply_status_time_fields(
        cls,
        *,
        ticket: "Ticket",
        from_status: str | None,
        to_status: str,
        update_data: dict[str, Any],
        now: datetime,
    ) -> None:
        """
        根据状态流转和结论字段补齐处理、发布、验证和处置时间。
        :param ticket: 当前工单。
        :param from_status: 原状态。
        :param to_status: 目标状态。
        :param update_data: 待更新字段字典。
        :param now: 当前时间。
        :return: 无，直接修改 update_data。
        """
        if not getattr(ticket, "processed_at", None) and (
            to_status in cls.PROCESSED_STATUSES or cls.has_processing_conclusion(update_data)
        ):
            update_data["processed_at"] = now
        if not getattr(ticket, "released_at", None) and (
            to_status == TicketStatus.WAIT_VERIFY.value
            or (from_status == TicketStatus.WAIT_RELEASE.value and to_status == TicketStatus.WAIT_VERIFY.value)
        ):
            update_data["released_at"] = now
        if not getattr(ticket, "verified_at", None) and (
            from_status == TicketStatus.WAIT_VERIFY.value and to_status == TicketStatus.RESOLVED.value
        ):
            update_data["verified_at"] = now

    @classmethod
    def apply_event_time_fields(
        cls,
        *,
        ticket: "Ticket",
        event_type: str,
        content: str | None,
        event_data: dict[str, Any] | None,
        update_data: dict[str, Any],
        now: datetime,
    ) -> None:
        """
        根据人工事件补齐处理、发布、验证和归档时间。
        :param ticket: 当前工单。
        :param event_type: 事件类型。
        :param content: 事件说明。
        :param event_data: 结构化事件数据。
        :param update_data: 待更新字段字典。
        :param now: 当前时间。
        :return: 无，直接修改 update_data。
        """
        data = event_data if isinstance(event_data, dict) else {}
        has_content = bool(str(content or "").strip() or data)
        if not getattr(ticket, "processed_at", None) and event_type in cls.PROCESSING_EVENT_TYPES and has_content:
            update_data["processed_at"] = now
        if event_type == TicketEventType.DEPLOYED.value:
            update_data.setdefault("released_at", getattr(ticket, "released_at", None) or now)
            version = str(data.get("releasedVersion") or data.get("released_version") or "").strip()
            if version:
                update_data["released_version"] = version
        if event_type == TicketEventType.VERIFIED.value:
            update_data.setdefault("verified_at", getattr(ticket, "verified_at", None) or now)
        if event_type == TicketEventType.RESOLVED.value:
            update_data.setdefault("resolved_at", getattr(ticket, "resolved_at", None) or now)
        if event_type == TicketEventType.CLOSED.value:
            update_data.setdefault("closed_at", getattr(ticket, "closed_at", None) or now)

    @classmethod
    def rca_has_conclusion(cls, rca_data: dict[str, Any] | None) -> bool:
        """
        判断 RCA 是否包含有效排查结论。
        :param rca_data: RCA 字段字典。
        :return: 是否包含结论。
        """
        data = rca_data if isinstance(rca_data, dict) else {}
        for field in ("root_cause_detail", "investigation_process", "fix_solution", "verify_method"):
            if str(data.get(field) or "").strip():
                return True
        return False
