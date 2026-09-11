from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, func, or_
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
    def get_repo_mapping_by_project_and_version_id(
        cls, db: Session, project_id: int, version_id: int | None
    ) -> TicketAiRepoMapping | None:
        """根据项目和版本中心ID查询启用的仓库映射。"""
        if not version_id:
            return None
        query = db.query(TicketAiRepoMapping).filter(
            TicketAiRepoMapping.project_id == project_id,
            TicketAiRepoMapping.version_id == version_id,
            TicketAiRepoMapping.enabled.is_(True),
        )
        return query.order_by(TicketAiRepoMapping.is_default.desc(), TicketAiRepoMapping.update_time.desc()).first()

    @classmethod
    def build_repo_mapping_query(cls, db: Session, query: TicketAiRepoMappingQueryModel):
        """
        构建仓库映射查询，保持 ORM 实体供服务层完成版本中心编排。
        :param db: 数据库会话
        :param query: 查询参数
        :return: 分页结果或列表
        """
        mapping_query = (
            db.query(TicketAiRepoMapping)
            .filter(
                TicketAiRepoMapping.project_id == query.project_id if query.project_id else True,
                TicketAiRepoMapping.version_id == query.version_id if query.version_id else True,
                TicketAiRepoMapping.enabled == query.enabled if query.enabled is not None else True,
            )
            .filter(
                or_(
                    TicketAiRepoMapping.project_name.like(f"%{query.keyword}%"),
                    TicketAiRepoMapping.repo_url.like(f"%{query.keyword}%"),
                    TicketAiRepoMapping.branch_name.like(f"%{query.keyword}%"),
                )
                if query.keyword
                else True
            )
            .order_by(
                TicketAiRepoMapping.is_default.desc(),
                TicketAiRepoMapping.project_id.asc(),
                TicketAiRepoMapping.version_id.asc(),
                TicketAiRepoMapping.update_time.desc(),
            )
        )
        return mapping_query

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
                TicketAiAnalysisTask.version_id == query.version_id if query.version_id else True,
            )
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
        )
        return PageUtil.paginate(task_query, query.page_num, query.page_size, query.is_page)

    @classmethod
    def list_latest_tasks_by_ticket_ids(cls, db: Session, ticket_ids: list[int]) -> dict[int, TicketAiAnalysisTask]:
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
    def get_last_successful_task_by_ticket(cls, db: Session, ticket_id: int) -> TicketAiAnalysisTask | None:
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
    def get_latest_task_by_log_pull_record_id(
        cls, db: Session, log_pull_record_id: int
    ) -> TicketAiAnalysisTask | None:
        """
        按来源日志拉取记录ID查询最新 AI 分析任务。
        用于自动链路判断某条成功日志记录是否已经执行过 AI 分析。
        :param db: 数据库会话
        :param log_pull_record_id: 日志拉取记录ID
        :return: 最新 AI 分析任务，无匹配时返回 None
        """
        if not log_pull_record_id:
            return None
        return (
            db.query(TicketAiAnalysisTask)
            .filter(TicketAiAnalysisTask.source_log_pull_record_id == log_pull_record_id)
            .order_by(TicketAiAnalysisTask.create_time.desc(), TicketAiAnalysisTask.task_id.desc())
            .first()
        )

    @classmethod
    def get_successful_task_by_request_fingerprint(
        cls, db: Session, request_fingerprint: str
    ) -> TicketAiAnalysisTask | None:
        """
        按分析请求指纹查询已经成功的任务。
        :param db: 数据库会话
        :param request_fingerprint: 分析请求指纹
        :return: 唯一成功任务，无匹配时返回 None
        """
        fingerprint = str(request_fingerprint or "").strip()
        if not fingerprint:
            return None
        return (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.request_fingerprint == fingerprint,
                TicketAiAnalysisTask.status == TicketAiAnalysisStatus.SUCCESS.value,
                TicketAiAnalysisTask.success_fingerprint == fingerprint,
            )
            .order_by(TicketAiAnalysisTask.finished_at.desc(), TicketAiAnalysisTask.task_id.desc())
            .first()
        )

    @classmethod
    def get_active_task_by_request_fingerprint(
        cls, db: Session, request_fingerprint: str
    ) -> TicketAiAnalysisTask | None:
        """
        查询同一分析请求当前正在执行或等待执行的任务。
        :param db: 数据库会话
        :param request_fingerprint: 分析请求指纹
        :return: 活跃任务，无匹配时返回 None
        """
        fingerprint = str(request_fingerprint or "").strip()
        if not fingerprint:
            return None
        return (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.request_fingerprint == fingerprint,
                TicketAiAnalysisTask.status.in_(
                    (TicketAiAnalysisStatus.CREATED.value, TicketAiAnalysisStatus.RUNNING.value)
                ),
            )
            .order_by(TicketAiAnalysisTask.create_time.asc(), TicketAiAnalysisTask.task_id.asc())
            .first()
        )

    @classmethod
    def get_ticket_token_summary(cls, db: Session, ticket_id: int) -> dict[str, int]:
        """
        按工单聚合 AI Token 使用量。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: Token 汇总字典
        """
        row = (
            db.query(
                func.coalesce(func.sum(TicketAiAnalysisTask.input_token_count), 0).label("input_token_count"),
                func.coalesce(func.sum(TicketAiAnalysisTask.output_token_count), 0).label("output_token_count"),
                func.coalesce(func.sum(TicketAiAnalysisTask.total_token_count), 0).label("total_token_count"),
                func.count(TicketAiAnalysisTask.task_id).label("task_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (TicketAiAnalysisTask.status == TicketAiAnalysisStatus.SUCCESS.value, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("success_task_count"),
            )
            .filter(TicketAiAnalysisTask.ticket_id == ticket_id)
            .one()
        )
        return {
            "input_token_count": int(getattr(row, "input_token_count", 0) or 0),
            "output_token_count": int(getattr(row, "output_token_count", 0) or 0),
            "total_token_count": int(getattr(row, "total_token_count", 0) or 0),
            "task_count": int(getattr(row, "task_count", 0) or 0),
            "success_task_count": int(getattr(row, "success_task_count", 0) or 0),
        }

    @classmethod
    def list_recoverable_tasks(cls, db: Session, statuses: list[str]) -> list[TicketAiAnalysisTask]:
        """
        查询需要恢复执行的 AI 分析任务。
        :param db: 数据库会话
        :param statuses: 可恢复状态列表
        :return: 任务列表（大列为延迟加载）
        """
        status_list = [status for status in statuses if status]
        if not status_list:
            return []
        return (
            db.query(TicketAiAnalysisTask)
            .options(
                defer(TicketAiAnalysisTask.prompt_text),
                defer(TicketAiAnalysisTask.raw_output),
                defer(TicketAiAnalysisTask.analysis_context),
            )
            .filter(TicketAiAnalysisTask.status.in_(status_list))
            .order_by(TicketAiAnalysisTask.create_time.asc(), TicketAiAnalysisTask.task_id.asc())
            .all()
        )

    @classmethod
    def is_result_replied(cls, db: Session, task_id: int | None) -> bool:
        """
        判断 AI 分析任务的结果是否已回帖到工单群话题（任务级幂等判定）。
        替代原 extra_data.external_sync.sync_state.ai_result_reply_task_ids JSON 列表（2026-09 拆表）。
        :param db: 数据库会话
        :param task_id: AI任务ID
        :return: 是否已回帖
        """
        if not task_id:
            return False
        row = (
            db.query(TicketAiAnalysisTask.result_replied_at)
            .filter(TicketAiAnalysisTask.task_id == task_id)
            .first()
        )
        if not row:
            return False
        return row[0] is not None

    @classmethod
    def mark_result_replied(cls, db: Session, task_id: int | None, chat_ids: list[str] | None = None) -> bool:
        """
        标记 AI 分析任务结果已回帖（条件更新保证并发下只有一个写者生效）。
        由调用方事务边界统一提交；任务不存在或已标记时返回 False。
        :param db: 数据库会话
        :param task_id: AI任务ID
        :param chat_ids: 本次回帖覆盖的群 chat_id 列表（审计用）
        :return: 是否本次标记成功
        """
        if not task_id:
            return False
        chat_text = ",".join(str(item or "").strip() for item in (chat_ids or []) if str(item or "").strip())[:512]
        updated = (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.task_id == task_id,
                TicketAiAnalysisTask.result_replied_at.is_(None),
            )
            .update(
                {
                    TicketAiAnalysisTask.result_replied_at: datetime.now(),
                    TicketAiAnalysisTask.result_replied_chat_ids: chat_text or None,
                },
                synchronize_session=False,
            )
        )
        return int(updated or 0) > 0

    @classmethod
    def has_any_result_replied(cls, db: Session, ticket_id: int) -> bool:
        """
        判断工单是否有过任意一次成功回帖（工单级幂等判定，oncePerTicket 配置使用）。
        :param db: 数据库会话
        :param ticket_id: 工单ID
        :return: 是否回帖过
        """
        if not ticket_id:
            return False
        row = (
            db.query(TicketAiAnalysisTask.task_id)
            .filter(
                TicketAiAnalysisTask.ticket_id == ticket_id,
                TicketAiAnalysisTask.result_replied_at.isnot(None),
            )
            .first()
        )
        return row is not None

    @classmethod
    def release_result_replied(cls, db: Session, task_id: int | None) -> bool:
        """
        释放回帖幂等占坑（置回 result_replied_at 为 NULL）。
        抢占式标记的失败补偿：占坑后全部群发送失败时调用，允许后续重试再次回帖。
        :param db: 数据库会话
        :param task_id: AI任务ID
        :return: 是否释放成功
        """
        if not task_id:
            return False
        updated = (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.task_id == task_id,
                TicketAiAnalysisTask.result_replied_at.isnot(None),
            )
            .update(
                {
                    TicketAiAnalysisTask.result_replied_at: None,
                    TicketAiAnalysisTask.result_replied_chat_ids: None,
                },
                synchronize_session=False,
            )
        )
        return int(updated or 0) > 0

    @classmethod
    def update_result_replied_chat_ids(cls, db: Session, task_id: int | None, chat_ids: str) -> bool:
        """
        回帖成功后补写覆盖群审计列（配合抢占式占坑：占坑时未知覆盖群，发送成功后回填）。
        :param db: 数据库会话
        :param task_id: AI任务ID
        :param chat_ids: 逗号分隔的群 chat_id 文本
        :return: 是否更新成功
        """
        if not task_id:
            return False
        updated = (
            db.query(TicketAiAnalysisTask)
            .filter(
                TicketAiAnalysisTask.task_id == task_id,
                TicketAiAnalysisTask.result_replied_at.isnot(None),
            )
            .update(
                {TicketAiAnalysisTask.result_replied_chat_ids: (chat_ids or None)},
                synchronize_session=False,
            )
        )
        return int(updated or 0) > 0
