from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from modules.ticket.dao.ticket_dao import _date_end, _date_start
from modules.ticket.entity.do.ticket_do import Ticket, TicketEvent
from modules.ticket.entity.vo.ticket_vo import (
    TicketReleaseBatchUpdateModel,
    TicketVersionStatisticsQueryModel,
)
from modules.ticket.enums.ticket_enums import TicketEventType, TicketStatus
from modules.ticket.util.ticket_common_util import user_id as _user_id
from modules.ticket.util.ticket_common_util import user_name as _user_name
from utils.common_util import CamelCaseUtil


def _normalize_text_list(value: Any) -> list[str]:
    """
    将逗号分隔字符串或列表转换为去重后的文本列表。
    :param value: 原始查询值
    :return: 文本列表
    """
    if value is None or value == "":
        return []
    raw_items = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    result: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_int_list(value: Any) -> list[int]:
    """
    将逗号分隔字符串或列表转换为去重后的整数列表。
    :param value: 原始查询值
    :return: 整数列表
    """
    result: list[int] = []
    for item in _normalize_text_list(value):
        try:
            parsed = int(item)
        except Exception:
            continue
        if parsed not in result:
            result.append(parsed)
    return result


def _blank_to_unknown(value: Any) -> str:
    """
    将空版本或空维度值统一归入“未填写”。
    :param value: 原始值
    :return: 展示值
    """
    return str(value or "").strip() or "未填写"


def _is_open_ticket(ticket: Ticket) -> bool:
    """
    判断工单是否仍处于未关闭待处理范围。
    :param ticket: 工单对象
    :return: 是否未关闭
    """
    return str(ticket.status or "") not in {
        TicketStatus.CLOSED.value,
        TicketStatus.REJECTED.value,
        TicketStatus.NON_PROBLEM.value,
        TicketStatus.DESIGN_AS_EXPECTED.value,
        TicketStatus.USER_MISOPERATION.value,
        TicketStatus.DUPLICATED.value,
    }


class TicketReleaseService:
    """
    工单版本治理服务，负责批量维护版本字段和实时版本统计。
    """

    @classmethod
    def batch_update_release_fields(
        cls,
        query_db: Session,
        payload: TicketReleaseBatchUpdateModel,
        current_user: CurrentUserModel,
    ) -> CrudResponseModel:
        """
        批量维护工单版本治理字段，并为发版/验证动作写入工单事件。
        :param query_db: 数据库会话
        :param payload: 批量维护参数
        :param current_user: 当前登录用户
        :return: 批量处理结果
        """
        now = datetime.now()
        tickets = (
            query_db.query(Ticket)
            .filter(Ticket.del_flag == "0", Ticket.ticket_id.in_(payload.ticket_ids))
            .all()
        )
        ticket_map = {int(ticket.ticket_id): ticket for ticket in tickets}
        missing_ticket_ids = [ticket_id for ticket_id in payload.ticket_ids if ticket_id not in ticket_map]
        released_at = payload.released_at or (now if payload.mark_released else None)
        verified_at = payload.verified_at or (now if payload.mark_verified else None)
        update_fields: dict[str, Any] = {
            "update_by": _user_name(current_user),
            "update_time": now,
        }
        if payload.planned_fix_version is not None:
            update_fields["planned_fix_version"] = payload.planned_fix_version
        if payload.fixed_version is not None:
            update_fields["fixed_version"] = payload.fixed_version
        if payload.released_version is not None:
            update_fields["released_version"] = payload.released_version
        if released_at is not None:
            update_fields["released_at"] = released_at
        if verified_at is not None:
            update_fields["verified_at"] = verified_at

        updated_ids: list[int] = []
        for ticket in tickets:
            for field_name, field_value in update_fields.items():
                setattr(ticket, field_name, field_value)
            updated_ids.append(int(ticket.ticket_id))
            cls.add_release_events(
                query_db,
                ticket=ticket,
                payload=payload,
                released_at=released_at,
                verified_at=verified_at,
                current_user=current_user,
            )
        query_db.commit()
        return CrudResponseModel(
            is_success=True,
            message=f"已维护 {len(updated_ids)} 张工单",
            result={
                "updatedCount": len(updated_ids),
                "updatedTicketIds": updated_ids,
                "missingTicketIds": missing_ticket_ids,
            },
        )

    @classmethod
    def add_release_events(
        cls,
        query_db: Session,
        *,
        ticket: Ticket,
        payload: TicketReleaseBatchUpdateModel,
        released_at: datetime | None,
        verified_at: datetime | None,
        current_user: CurrentUserModel,
    ) -> None:
        """
        根据批量维护动作补充发版或验证事件。
        :param query_db: 数据库会话
        :param ticket: 被维护的工单
        :param payload: 批量维护参数
        :param released_at: 发版完成时间
        :param verified_at: 验证完成时间
        :param current_user: 当前登录用户
        :return: 无
        """
        event_data = {
            "planned_fix_version": payload.planned_fix_version,
            "fixed_version": payload.fixed_version,
            "released_version": payload.released_version,
            "released_at": released_at.isoformat(sep=" ") if released_at else None,
            "verified_at": verified_at.isoformat(sep=" ") if verified_at else None,
            "batch": True,
        }
        if released_at is not None:
            query_db.add(
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.DEPLOYED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=payload.comment or "批量标记发版完成",
                    event_data=event_data,
                    create_time=released_at,
                )
            )
        if verified_at is not None:
            query_db.add(
                TicketEvent(
                    ticket_id=ticket.ticket_id,
                    event_type=TicketEventType.VERIFIED.value,
                    operator_id=_user_id(current_user),
                    operator_name=_user_name(current_user),
                    content=payload.comment or "批量标记验证完成",
                    event_data=event_data,
                    create_time=verified_at,
                )
            )

    @classmethod
    def get_version_statistics(
        cls,
        query_db: Session,
        query: TicketVersionStatisticsQueryModel,
    ) -> dict[str, Any]:
        """
        按版本维度实时统计工单当前态。
        :param query_db: 数据库会话
        :param query: 版本统计筛选条件
        :return: 发生版本和修复/发版版本统计
        """
        tickets = cls.list_statistics_tickets(query_db, query)
        affected_rows = cls.build_version_rows(
            tickets,
            version_fields=("affected_version",),
            top_limit=query.top_limit,
            version_limit=query.version_limit,
        )
        fix_rows = cls.build_version_rows(
            tickets,
            version_fields=("planned_fix_version", "fixed_version", "released_version"),
            top_limit=query.top_limit,
            version_limit=query.version_limit,
        )
        return {
            "total": len(tickets),
            "affectedVersionRows": affected_rows,
            "fixVersionRows": fix_rows,
            "generatedAt": datetime.now(),
        }

    @classmethod
    def list_statistics_tickets(
        cls,
        query_db: Session,
        query: TicketVersionStatisticsQueryModel,
    ) -> list[Ticket]:
        """
        根据版本统计筛选条件查询工单，统计页只读取当前态，不修改数据。
        :param query_db: 数据库会话
        :param query: 筛选条件
        :return: 工单列表
        """
        create_begin_time = _date_start(query.begin_time)
        create_end_time = _date_end(query.end_time)
        submit_begin_time = _date_start(query.submit_begin_time)
        submit_end_time = _date_end(query.submit_end_time)
        processed_begin_time = _date_start(query.processed_begin_time)
        processed_end_time = _date_end(query.processed_end_time)
        project_ids = _normalize_int_list(query.project_ids)
        module_ids = _normalize_int_list(query.module_ids)
        issue_type_ids = _normalize_text_list(query.issue_type_ids)
        root_cause_types = _normalize_text_list(query.root_cause_types)
        solution_types = _normalize_text_list(query.solution_types)
        resolution_codes = _normalize_text_list(query.resolution_codes)
        problem_pattern_codes = _normalize_text_list(query.problem_pattern_codes)
        ticket_query = query_db.query(Ticket).filter(Ticket.del_flag == "0")
        if create_begin_time:
            ticket_query = ticket_query.filter(Ticket.create_time >= create_begin_time)
        if create_end_time:
            ticket_query = ticket_query.filter(Ticket.create_time <= create_end_time)
        if submit_begin_time:
            ticket_query = ticket_query.filter(Ticket.submit_time >= submit_begin_time)
        if submit_end_time:
            ticket_query = ticket_query.filter(Ticket.submit_time <= submit_end_time)
        if processed_begin_time:
            ticket_query = ticket_query.filter(Ticket.processed_at >= processed_begin_time)
        if processed_end_time:
            ticket_query = ticket_query.filter(Ticket.processed_at <= processed_end_time)
        if project_ids:
            ticket_query = ticket_query.filter(Ticket.project_id.in_(project_ids))
        if module_ids:
            ticket_query = ticket_query.filter(Ticket.module_id.in_(module_ids))
        if issue_type_ids:
            ticket_query = ticket_query.filter(Ticket.issue_type_id.in_(issue_type_ids))
        if root_cause_types:
            ticket_query = ticket_query.filter(Ticket.root_cause_type.in_(root_cause_types))
        if solution_types:
            ticket_query = ticket_query.filter(Ticket.solution_type.in_(solution_types))
        if resolution_codes:
            ticket_query = ticket_query.filter(Ticket.resolution_code.in_(resolution_codes))
        if problem_pattern_codes:
            ticket_query = ticket_query.filter(Ticket.problem_pattern_code.in_(problem_pattern_codes))
        if query.version_keyword:
            keyword = f"%{query.version_keyword}%"
            ticket_query = ticket_query.filter(
                or_(
                    Ticket.affected_version.like(keyword),
                    Ticket.planned_fix_version.like(keyword),
                    Ticket.fixed_version.like(keyword),
                    Ticket.released_version.like(keyword),
                )
            )
        return ticket_query.order_by(Ticket.update_time.desc(), Ticket.ticket_id.desc()).all()

    @classmethod
    def build_version_rows(
        cls,
        tickets: list[Ticket],
        *,
        version_fields: tuple[str, ...],
        top_limit: int,
        version_limit: int,
    ) -> list[dict[str, Any]]:
        """
        按指定版本字段聚合工单统计行。
        :param tickets: 工单列表
        :param version_fields: 参与聚合的版本字段
        :param top_limit: Top 维度数量
        :param version_limit: 版本行上限
        :return: 版本统计行
        """
        grouped: dict[str, list[Ticket]] = {}
        for ticket in tickets:
            version_values = {_blank_to_unknown(getattr(ticket, field_name, "")) for field_name in version_fields}
            for version in version_values:
                grouped.setdefault(version, []).append(ticket)
        rows = [
            cls.build_single_version_row(version, version_tickets, top_limit=top_limit)
            for version, version_tickets in grouped.items()
        ]
        rows.sort(key=lambda item: (item["version"] == "未填写", -item["ticket_count"], item["version"]))
        return [CamelCaseUtil.transform_result(row) for row in rows[:version_limit]]

    @classmethod
    def build_single_version_row(
        cls,
        version: str,
        tickets: list[Ticket],
        *,
        top_limit: int,
    ) -> dict[str, Any]:
        """
        构建单个版本统计行。
        :param version: 版本号
        :param tickets: 当前版本命中的工单
        :param top_limit: Top 维度数量
        :return: 统计行
        """
        issue_ids = {ticket.issue_id for ticket in tickets if ticket.issue_id}
        problem_tickets = [ticket for ticket in tickets if ticket.is_problem is True]
        processed_tickets = [ticket for ticket in tickets if ticket.processed_at]
        released_tickets = [ticket for ticket in tickets if ticket.released_at]
        verified_tickets = [ticket for ticket in tickets if ticket.verified_at]
        return {
            "version": version,
            "ticket_count": len(tickets),
            "problem_count": len(problem_tickets),
            "issue_count": len(issue_ids),
            "processed_count": len(processed_tickets),
            "unprocessed_count": max(len(tickets) - len(processed_tickets), 0),
            "open_backlog": sum(1 for ticket in tickets if _is_open_ticket(ticket)),
            "released_count": len(released_tickets),
            "verified_count": len(verified_tickets),
            "unverified_count": max(len(released_tickets) - len(verified_tickets), 0),
            "top_modules": cls.build_top_rows((ticket.module_name for ticket in tickets), top_limit),
            "top_issue_types": cls.build_top_rows((ticket.issue_type_name for ticket in tickets), top_limit),
            "top_problem_patterns": cls.build_top_rows(
                (ticket.problem_pattern_name or ticket.problem_pattern_code for ticket in tickets),
                top_limit,
            ),
            "top_root_causes": cls.build_top_rows((ticket.root_cause_type for ticket in tickets), top_limit),
            "solution_type_counts": cls.build_top_rows((ticket.solution_type for ticket in tickets), top_limit),
            "resolution_counts": cls.build_top_rows(
                (ticket.resolution_name or ticket.resolution_code for ticket in tickets),
                top_limit,
            ),
        }

    @classmethod
    def build_top_rows(cls, values, top_limit: int) -> list[dict[str, Any]]:
        """
        将维度值聚合为 TopN 计数。
        :param values: 维度值迭代器
        :param top_limit: 返回数量
        :return: TopN 行
        """
        counter = Counter(_blank_to_unknown(value) for value in values)
        return [
            {"name": name, "count": count}
            for name, count in counter.most_common(top_limit)
            if name != "未填写" or count > 0
        ]
