from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from modules.ticket.entity.do.ticket_do import TicketStatisticsDaily


class TicketStatisticsDailyDao:
    """
    工单每日快照数据访问层。
    """

    @classmethod
    def get_by_scope(
        cls,
        db: Session,
        statistics_date: date,
        *,
        snapshot_scope: str = "all",
        project_id: int | None = None,
        module_id: int | None = None,
        issue_type_id: str | None = None,
    ) -> TicketStatisticsDaily | None:
        """
        按日期和维度获取每日快照。
        :param db: 数据库会话。
        :param statistics_date: 统计日期。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_id: 项目ID，空值按 0 归一。
        :param module_id: 模块ID，空值按 0 归一。
        :param issue_type_id: 工单类型编码，空值按空字符串归一。
        :return: 每日快照记录。
        """
        return (
            db.query(TicketStatisticsDaily)
            .filter(
                TicketStatisticsDaily.statistics_date == statistics_date,
                TicketStatisticsDaily.snapshot_scope == str(snapshot_scope or "all").strip().lower(),
                TicketStatisticsDaily.project_id == int(project_id or 0),
                TicketStatisticsDaily.module_id == int(module_id or 0),
                TicketStatisticsDaily.issue_type_id == str(issue_type_id or "").strip(),
            )
            .one_or_none()
        )

    @classmethod
    def upsert_by_scope(
        cls,
        db: Session,
        statistics_date: date,
        payload: dict[str, Any],
        *,
        snapshot_scope: str = "all",
        project_id: int | None = None,
        module_id: int | None = None,
        issue_type_id: str | None = None,
    ) -> TicketStatisticsDaily:
        """
        按日期和维度写入或更新每日快照。
        :param db: 数据库会话。
        :param statistics_date: 统计日期。
        :param payload: 聚合结果。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_id: 项目ID，空值按 0 归一。
        :param module_id: 模块ID，空值按 0 归一。
        :param issue_type_id: 工单类型编码，空值按空字符串归一。
        :return: 写入后的快照记录。
        """
        normalized_scope = str(snapshot_scope or "all").strip().lower()
        normalized_project_id = int(project_id or 0)
        normalized_module_id = int(module_id or 0)
        normalized_issue_type_id = str(issue_type_id or "").strip()
        row = cls.get_by_scope(
            db,
            statistics_date,
            snapshot_scope=normalized_scope,
            project_id=normalized_project_id,
            module_id=normalized_module_id,
            issue_type_id=normalized_issue_type_id,
        )
        if row is None:
            row = TicketStatisticsDaily(
                statistics_date=statistics_date,
                snapshot_scope=normalized_scope,
                project_id=normalized_project_id,
                module_id=normalized_module_id,
                issue_type_id=normalized_issue_type_id,
                create_time=datetime.now(),
            )
            db.add(row)
        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)
        db.flush()
        return row

    @classmethod
    def list_between(
        cls,
        db: Session,
        begin_date: date | None,
        end_date: date | None,
        *,
        snapshot_scope: str | None = None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        automation_scope_module_ids: list[int] | None = None,
        automation_scope_module_name_includes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
    ) -> list[TicketStatisticsDaily]:
        """
        查询日期范围内的每日快照。
        :param db: 数据库会话。
        :param begin_date: 开始日期。
        :param end_date: 结束日期。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_ids: 项目ID过滤。
        :param module_ids: 模块ID过滤。
        :param module_codes: 模块业务码过滤。
        :param automation_scope_module_ids: 自动化关注范围已解析的模块 ID。
        :param automation_scope_module_name_includes: 自动化关注范围模块名称关键字。
        :param issue_type_ids: 工单类型编码过滤。
        :return: 快照列表。
        """
        query = db.query(TicketStatisticsDaily)
        if begin_date is not None:
            query = query.filter(TicketStatisticsDaily.statistics_date >= begin_date)
        if end_date is not None:
            query = query.filter(TicketStatisticsDaily.statistics_date <= end_date)
        if snapshot_scope:
            query = query.filter(TicketStatisticsDaily.snapshot_scope == str(snapshot_scope).strip().lower())
        if project_ids:
            query = query.filter(TicketStatisticsDaily.project_id.in_(project_ids))
        if module_ids:
            query = query.filter(TicketStatisticsDaily.module_id.in_(module_ids))
        if module_codes:
            normalized_codes = [str(item or "").strip() for item in module_codes if str(item or "").strip()]
            if normalized_codes:
                query = query.filter(TicketStatisticsDaily.module_code.in_(normalized_codes))
        if automation_scope_module_ids is not None or automation_scope_module_name_includes is not None:
            scope_conditions = []
            if automation_scope_module_ids:
                scope_conditions.append(TicketStatisticsDaily.module_id.in_(automation_scope_module_ids))
            for keyword in automation_scope_module_name_includes or []:
                text = str(keyword or "").strip()
                if text:
                    scope_conditions.append(func.lower(TicketStatisticsDaily.module_name).like(f"%{text.casefold()}%"))
            query = query.filter(or_(*scope_conditions) if scope_conditions else TicketStatisticsDaily.id == -1)
        if issue_type_ids:
            normalized_issue_type_ids = [str(item or "").strip() for item in issue_type_ids if str(item or "").strip()]
            if normalized_issue_type_ids:
                query = query.filter(TicketStatisticsDaily.issue_type_id.in_(normalized_issue_type_ids))
        return query.order_by(
            TicketStatisticsDaily.statistics_date.asc(),
            TicketStatisticsDaily.project_id.asc(),
            TicketStatisticsDaily.module_id.asc(),
            TicketStatisticsDaily.issue_type_id.asc(),
        ).all()

    @classmethod
    def build_module_code_map(cls, db: Session, module_ids: list[int]) -> dict[int, str]:
        """
        批量查询模块业务码。
        :param db: 数据库会话。
        :param module_ids: 模块ID列表。
        :return: module_id -> module_code 映射。
        """
        normalized_ids = sorted({int(item) for item in module_ids if item})
        if not normalized_ids:
            return {}
        rows = (
            db.query(HrmModule.module_id, HrmModule.module_code)
            .filter(HrmModule.module_id.in_(normalized_ids))
            .all()
        )
        return {int(row[0]): str(row[1] or "").strip() for row in rows if row[0]}

    @classmethod
    def build_project_name_map(cls, db: Session, project_ids: list[int]) -> dict[int, str]:
        """
        批量查询项目名称。
        :param db: 数据库会话。
        :param project_ids: 项目ID列表。
        :return: project_id -> project_name 映射。
        """
        normalized_ids = sorted({int(item) for item in project_ids if item})
        if not normalized_ids:
            return {}
        rows = (
            db.query(HrmProject.project_id, HrmProject.project_name)
            .filter(HrmProject.project_id.in_(normalized_ids))
            .all()
        )
        return {int(row[0]): str(row[1] or "").strip() for row in rows if row[0]}
