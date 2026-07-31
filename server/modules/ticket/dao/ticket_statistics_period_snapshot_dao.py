from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from modules.ticket.entity.do.ticket_do import TicketStatisticsPeriodSnapshot


class TicketStatisticsPeriodSnapshotDao:
    """
    工单周期快照数据访问层。
    """

    PERIOD_TYPE_BUSINESS_WEEK = "business_week"

    @classmethod
    def get_by_scope(
        cls,
        db: Session,
        period_type: str,
        period_start_time: datetime,
        *,
        snapshot_scope: str = "all",
        project_id: int | None = None,
        module_id: int | None = None,
        issue_type_id: str | None = None,
    ) -> TicketStatisticsPeriodSnapshot | None:
        """
        按周期和维度获取周期快照。
        :param db: 数据库会话。
        :param period_type: 周期类型。
        :param period_start_time: 周期开始时间。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_id: 项目ID，空值按 0 归一。
        :param module_id: 模块ID，空值按 0 归一。
        :param issue_type_id: 工单类型编码，空值按空字符串归一。
        :return: 周期快照记录。
        """
        return (
            db.query(TicketStatisticsPeriodSnapshot)
            .filter(
                TicketStatisticsPeriodSnapshot.period_type == str(period_type or "").strip().lower(),
                TicketStatisticsPeriodSnapshot.period_start_time == period_start_time,
                TicketStatisticsPeriodSnapshot.snapshot_scope == str(snapshot_scope or "all").strip().lower(),
                TicketStatisticsPeriodSnapshot.project_id == int(project_id or 0),
                TicketStatisticsPeriodSnapshot.module_id == int(module_id or 0),
                TicketStatisticsPeriodSnapshot.issue_type_id == str(issue_type_id or "").strip(),
            )
            .one_or_none()
        )

    @classmethod
    def upsert_by_scope(
        cls,
        db: Session,
        period_type: str,
        period_start_time: datetime,
        period_end_time: datetime,
        payload: dict[str, Any],
        *,
        snapshot_scope: str = "all",
        project_id: int | None = None,
        module_id: int | None = None,
        issue_type_id: str | None = None,
    ) -> TicketStatisticsPeriodSnapshot:
        """
        按周期和维度写入或更新周期快照。
        :param db: 数据库会话。
        :param period_type: 周期类型。
        :param period_start_time: 周期开始时间。
        :param period_end_time: 周期结束时间。
        :param payload: 聚合结果。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_id: 项目ID，空值按 0 归一。
        :param module_id: 模块ID，空值按 0 归一。
        :param issue_type_id: 工单类型编码，空值按空字符串归一。
        :return: 写入后的周期快照记录。
        """
        normalized_period_type = str(period_type or cls.PERIOD_TYPE_BUSINESS_WEEK).strip().lower()
        normalized_scope = str(snapshot_scope or "all").strip().lower()
        normalized_project_id = int(project_id or 0)
        normalized_module_id = int(module_id or 0)
        normalized_issue_type_id = str(issue_type_id or "").strip()
        row = cls.get_by_scope(
            db,
            normalized_period_type,
            period_start_time,
            snapshot_scope=normalized_scope,
            project_id=normalized_project_id,
            module_id=normalized_module_id,
            issue_type_id=normalized_issue_type_id,
        )
        if row is None:
            row = TicketStatisticsPeriodSnapshot(
                period_type=normalized_period_type,
                period_key=period_start_time.date().isoformat(),
                period_start_time=period_start_time,
                period_end_time=period_end_time,
                snapshot_scope=normalized_scope,
                project_id=normalized_project_id,
                module_id=normalized_module_id,
                issue_type_id=normalized_issue_type_id,
                create_time=datetime.now(),
            )
            db.add(row)
        row.period_end_time = period_end_time
        row.period_key = str(payload.get("period_key") or period_start_time.date().isoformat())
        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)
        db.flush()
        return row

    @classmethod
    def list_between(
        cls,
        db: Session,
        begin_time: datetime | None,
        end_time: datetime | None,
        *,
        period_type: str = PERIOD_TYPE_BUSINESS_WEEK,
        snapshot_scope: str | None = None,
        project_ids: list[int] | None = None,
        module_ids: list[int] | None = None,
        module_codes: list[str] | None = None,
        automation_scope_module_ids: list[int] | None = None,
        automation_scope_module_name_includes: list[str] | None = None,
        issue_type_ids: list[str] | None = None,
    ) -> list[TicketStatisticsPeriodSnapshot]:
        """
        查询周期开始时间落在指定范围内的周期快照。
        :param db: 数据库会话。
        :param begin_time: 查询开始时间。
        :param end_time: 查询结束时间。
        :param period_type: 周期类型。
        :param snapshot_scope: 快照范围，all 或 leaf。
        :param project_ids: 项目ID过滤。
        :param module_ids: 模块ID过滤。
        :param module_codes: 模块业务码过滤。
        :param automation_scope_module_ids: 自动化关注范围已解析的模块 ID。
        :param automation_scope_module_name_includes: 自动化关注范围模块名称关键字。
        :param issue_type_ids: 工单类型编码过滤。
        :return: 周期快照列表。
        """
        query = db.query(TicketStatisticsPeriodSnapshot).filter(
            TicketStatisticsPeriodSnapshot.period_type == str(period_type or "").strip().lower()
        )
        if begin_time is not None:
            query = query.filter(TicketStatisticsPeriodSnapshot.period_start_time >= begin_time)
        if end_time is not None:
            query = query.filter(TicketStatisticsPeriodSnapshot.period_start_time <= end_time)
        if snapshot_scope:
            query = query.filter(TicketStatisticsPeriodSnapshot.snapshot_scope == str(snapshot_scope).strip().lower())
        if project_ids:
            query = query.filter(TicketStatisticsPeriodSnapshot.project_id.in_(project_ids))
        if module_ids:
            query = query.filter(TicketStatisticsPeriodSnapshot.module_id.in_(module_ids))
        if module_codes:
            normalized_codes = [str(item or "").strip() for item in module_codes if str(item or "").strip()]
            if normalized_codes:
                query = query.filter(TicketStatisticsPeriodSnapshot.module_code.in_(normalized_codes))
        if automation_scope_module_ids is not None or automation_scope_module_name_includes is not None:
            scope_conditions = []
            if automation_scope_module_ids:
                scope_conditions.append(TicketStatisticsPeriodSnapshot.module_id.in_(automation_scope_module_ids))
            for keyword in automation_scope_module_name_includes or []:
                text = str(keyword or "").strip()
                if text:
                    scope_conditions.append(
                        func.lower(TicketStatisticsPeriodSnapshot.module_name).like(f"%{text.casefold()}%")
                    )
            query = query.filter(
                or_(*scope_conditions) if scope_conditions else TicketStatisticsPeriodSnapshot.id == -1
            )
        if issue_type_ids:
            normalized_issue_type_ids = [str(item or "").strip() for item in issue_type_ids if str(item or "").strip()]
            if normalized_issue_type_ids:
                query = query.filter(TicketStatisticsPeriodSnapshot.issue_type_id.in_(normalized_issue_type_ids))
        return query.order_by(
            TicketStatisticsPeriodSnapshot.period_start_time.asc(),
            TicketStatisticsPeriodSnapshot.project_id.asc(),
            TicketStatisticsPeriodSnapshot.module_id.asc(),
            TicketStatisticsPeriodSnapshot.issue_type_id.asc(),
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
