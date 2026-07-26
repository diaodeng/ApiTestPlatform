from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session, defer

from modules.ticket.entity.do.ticket_do import TicketAiAnalysisTask, TicketAiRepoMapping
from modules.ticket.entity.vo.ticket_vo import TicketAiAnalysisTaskQueryModel, TicketAiRepoMappingQueryModel
from modules.ticket.enums.ticket_enums import TicketAiAnalysisStatus
from utils.page_util import PageUtil


class TicketAiDao:
    """
    工单 AI 分析数据访问层，负责仓库映射和分析任务的基础增删查改。
    """

    @classmethod
    def get_repo_mapping_by_id(cls, db: Session, mapping_id: int) -> TicketAiRepoMapping | None:
        """
        根据映射ID查询仓库映射。
        :param db: 数据库会话
        :param mapping_id: 映射ID
        :return: 仓库映射对象
        """
        return db.query(TicketAiRepoMapping).filter(TicketAiRepoMapping.mapping_id == mapping_id).first()

    @classmethod
    def get_repo_mapping_by_project_and_version(
        cls, db: Session, project_id: int, version_key: str | None
    ) -> TicketAiRepoMapping | None:
        """
        根据项目和版本查询仓库映射。
        :param db: 数据库会话
        :param project_id: 项目ID
        :param version_key: 版本标识
        :return: 仓库映射对象
        """
        version_text = str(version_key or "").strip()
        if not version_text:
            return None
        query = db.query(TicketAiRepoMapping).filter(
            TicketAiRepoMapping.project_id == project_id,
            TicketAiRepoMapping.enabled.is_(True),
            TicketAiRepoMapping.version_key == version_text,
        )
        mapping = query.filter(TicketAiRepoMapping.is_default.is_(True)).first()
        if mapping:
            return mapping
        return (
            query
            .order_by(TicketAiRepoMapping.is_default.desc(), TicketAiRepoMapping.update_time.desc())
            .first()
        )

    @classmethod
    def list_repo_mappings(cls, db: Session, query: TicketAiRepoMappingQueryModel):
        """
        分页查询仓库映射列表。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        mapping_query = (
            db.query(TicketAiRepoMapping)
            .filter(
                TicketAiRepoMapping.project_id == query.project_id if query.project_id else True,
                TicketAiRepoMapping.version_key == query.version_key if query.version_key else True,
                TicketAiRepoMapping.enabled == query.enabled if query.enabled is not None else True,
            )
            .filter(
                or_(
                    TicketAiRepoMapping.project_name.like(f"%{query.keyword}%"),
                    TicketAiRepoMapping.version_key.like(f"%{query.keyword}%"),
                    TicketAiRepoMapping.repo_url.like(f"%{query.keyword}%"),
                    TicketAiRepoMapping.branch_name.like(f"%{query.keyword}%"),
                )
                if query.keyword
                else True
            )
            .order_by(
                TicketAiRepoMapping.is_default.desc(),
                TicketAiRepoMapping.project_id.asc(),
                TicketAiRepoMapping.version_key.asc(),
                TicketAiRepoMapping.update_time.desc(),
            )
        )
        return PageUtil.paginate(mapping_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def add_repo_mapping(cls, db: Session, mapping: TicketAiRepoMapping) -> TicketAiRepoMapping:
        """
        新增仓库映射。
        :param db: 数据库会话
        :param mapping: 映射对象
        :return: 保存后的映射对象
        """
        db.add(mapping)
        db.flush()
        return mapping

    @classmethod
    def update_repo_mapping(cls, db: Session, mapping_id: int, data: dict) -> None:
        """
        更新仓库映射。
        :param db: 数据库会话
        :param mapping_id: 映射ID
        :param data: 更新字段
        :return: 无
        """
        db.query(TicketAiRepoMapping).filter(TicketAiRepoMapping.mapping_id == mapping_id).update(data)

    @classmethod
    def delete_repo_mapping(cls, db: Session, mapping_id: int) -> None:
        """
        删除仓库映射。
        :param db: 数据库会话
        :param mapping_id: 映射ID
        :return: 无
        """
        db.query(TicketAiRepoMapping).filter(TicketAiRepoMapping.mapping_id == mapping_id).delete()

    @classmethod
    def get_task_by_id(cls, db: Session, task_id: int) -> TicketAiAnalysisTask | None:
        """
        根据任务ID查询分析任务。
        :param db: 数据库会话
        :param task_id: 任务ID
        :return: 任务对象
        """
        return db.query(TicketAiAnalysisTask).filter(TicketAiAnalysisTask.task_id == task_id).first()

    @classmethod
    def add_task(cls, db: Session, task: TicketAiAnalysisTask) -> TicketAiAnalysisTask:
        """
        新增分析任务。
        :param db: 数据库会话
        :param task: 任务对象
        :return: 任务对象
        """
        db.add(task)
        db.flush()
        return task

    @classmethod
    def update_task(cls, db: Session, task_id: int, data: dict) -> None:
        """
        更新分析任务。
        :param db: 数据库会话
        :param task_id: 任务ID
        :param data: 更新字段
        :return: 无
        """
        db.query(TicketAiAnalysisTask).filter(TicketAiAnalysisTask.task_id == task_id).update(data)

    @classmethod
    def list_ticket_tasks(cls, db: Session, ticket_id: int, query: TicketAiAnalysisTaskQueryModel):
        """
        分页查询工单 AI 分析任务。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :param query: 查询参数
        :return: 分页结果或列表
        """
        task_query = (
            db.query(TicketAiAnalysisTask)
            .options(
                defer(TicketAiAnalysisTask.prompt_text),
                defer(TicketAiAnalysisTask.raw_output),
                defer(TicketAiAnalysisTask.analysis_context),
            )
            .filter(
                TicketAiAnalysisTask.ticket_id == ticket_id,
                TicketAiAnalysisTask.status == query.status if query.status else True,
                TicketAiAnalysisTask.version_key == query.version_key if query.version_key else True,
            )
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
        )
        return PageUtil.paginate(task_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_latest_tasks_by_ticket_ids(
        cls, db: Session, ticket_ids: list[int]
    ) -> dict[int, TicketAiAnalysisTask]:
        """
        查询多个工单最新一条 AI 分析任务。
        :param db: 数据库会话
        :param ticket_ids: 工单ID列表
        :return: 以工单ID为键的最新任务映射
        """
        ticket_id_list = [ticket_id for ticket_id in ticket_ids if ticket_id]
        if not ticket_id_list:
            return {}
        rows = (
            db.query(TicketAiAnalysisTask)
            .options(
                defer(TicketAiAnalysisTask.prompt_text),
                defer(TicketAiAnalysisTask.raw_output),
                defer(TicketAiAnalysisTask.analysis_context),
            )
            .filter(TicketAiAnalysisTask.ticket_id.in_(ticket_id_list))
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
            .all()
        )
        task_map: dict[int, TicketAiAnalysisTask] = {}
        for row in rows:
            task_map.setdefault(row.ticket_id, row)
        return task_map

    @classmethod
    def get_latest_task_by_ticket_id(cls, db: Session, ticket_id: int) -> TicketAiAnalysisTask | None:
        """
        查询单个工单最新 AI 分析任务。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 最新任务
        """
        return (
            db.query(TicketAiAnalysisTask)
            .filter(TicketAiAnalysisTask.ticket_id == ticket_id)
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
            .first()
        )

    @classmethod
    def get_last_successful_task_by_ticket(
        cls, db: Session, ticket_id: int
    ) -> TicketAiAnalysisTask | None:
        """
        查询工单最近一次成功的 AI 分析任务。
        用于 resume 时获取上次任务会话数据。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 最近成功的任务，无成功记录时返回 None
        """
        return (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.ticket_id == ticket_id,
                TicketAiAnalysisTask.status == TicketAiAnalysisStatus.SUCCESS.value,
            )
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
            .first()
        )

    @classmethod
    def list_recoverable_tasks(cls, db: Session, statuses: list[str]) -> list[TicketAiAnalysisTask]:
        """
        查询需要恢复执行的 AI 分析任务。
        :param db: 数据库会话
        :param statuses: 可恢复状态列表
        :return: 任务列表
        """
        status_list = [status for status in statuses if status]
        if not status_list:
            return []
        return (
            db.query(TicketAiAnalysisTask)
            .filter(TicketAiAnalysisTask.status.in_(status_list))
            .order_by(TicketAiAnalysisTask.create_time.asc(), TicketAiAnalysisTask.task_id.asc())
            .all()
        )
