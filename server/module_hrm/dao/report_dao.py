from datetime import date, datetime, time

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.do.run_error_do import HrmRunError
from module_hrm.entity.vo.report_vo import ReportCreatModel, ReportDelModel, ReportListModel, ReportQueryModel
from module_hrm.enums.enums import CaseRunStatus
from utils.page_util import PageUtil


class ReportDao:
    """
    报告数据库操作层
    """

    @classmethod
    async def get_by_id(cls, db: Session, report_id: int) -> HrmReport|None:
        def _query(db: Session, report_id: int):
            return db.query(HrmReport).filter(HrmReport.report_id == report_id).first()

        return await run_in_threadpool(_query, db, report_id)

    @classmethod
    def get_by_name(cls, db: Session, report_name: str):
        pass

    @classmethod
    def generate_report(cls, db: Session, report_name: str, report_content: str):
        pass

    @classmethod
    async def update(cls, db: Session, report_id: int, success: int, total: int, status: CaseRunStatus):
        report = await cls.get_by_id(db, report_id)

        if not report:
            return
        duration = (datetime.now() - datetime.fromtimestamp(report.start_at.timestamp())).total_seconds()
        report.success = success
        report.total = total
        report.test_duration = duration
        report.status = status.value
        await run_in_threadpool(db.commit)

    @classmethod
    def _delete_sync(cls, db: Session, report_ids: list, batch_size: int = 5000):
        """
        同步删除报告及其明细、错误记录。

        :param db: 数据库会话。
        :param report_ids: 报告ID列表。
        :param batch_size: 每批处理的明细数量。
        :return: 删除的报告数量。
        """
        try:
            if not report_ids:
                return 0
            while True:
                ids = (
                    db.query(HrmRunDetail.detail_id)
                    .filter(HrmRunDetail.report_id.in_(report_ids))
                    .limit(batch_size)
                    .all()
                )

                if not ids:
                    break

                id_list = [i[0] for i in ids]

                db.query(HrmRunError).filter(HrmRunError.detail_id.in_(id_list)).delete(synchronize_session=False)
                db.query(HrmRunDetail).filter(HrmRunDetail.detail_id.in_(id_list)).delete(synchronize_session=False)

                db.commit()  # 每批提交一次

            # 删除主表（一般量小）
            db.query(HrmReport).filter(HrmReport.report_id.in_(report_ids)).delete(synchronize_session=False)

            db.commit()
            return len(report_ids)

        except:
            db.rollback()
            raise

    @classmethod
    async def delete(cls, db: Session, report_ids: list):
        """
        根据报告ID列表删除测试报告。

        :param db: 数据库会话。
        :param report_ids: 报告ID列表。
        :return: 删除的报告数量。
        """
        if not report_ids:
            return 0
        return await run_in_threadpool(cls._delete_sync, db, report_ids)

    @classmethod
    def _normalize_cleanup_time(cls, raw_value):
        """
        归一化清理时间参数为 datetime。

        :param raw_value: 日期、时间或字符串。
        :return: datetime 或 None。
        """
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, datetime):
            return raw_value
        if isinstance(raw_value, date):
            return datetime.combine(raw_value, time.min)
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return datetime.combine(date.fromisoformat(text[:10]), time.min)

    @classmethod
    def _collect_cleanup_report_ids_sync(
        cls,
        db: Session,
        report_ids: list | None = None,
        user_id: int | None = None,
        begin_time=None,
        end_time=None,
    ) -> list[int]:
        """
        根据报告ID、用户ID和时间范围筛选待删除报告ID。

        :param db: 数据库会话。
        :param report_ids: 报告ID列表。
        :param user_id: 用户ID，过滤 manager 字段。
        :param begin_time: 开始时间。
        :param end_time: 结束时间。
        :return: 待删除的报告ID列表。
        """
        query = db.query(HrmReport.report_id)
        normalized_ids = [int(item) for item in (report_ids or []) if str(item or "").strip()]
        if normalized_ids:
            query = query.filter(HrmReport.report_id.in_(normalized_ids))
        if user_id is not None:
            query = query.filter(HrmReport.manager == int(user_id))
        start_at = cls._normalize_cleanup_time(begin_time)
        end_at = cls._normalize_cleanup_time(end_time)
        if start_at and end_at:
            query = query.filter(HrmReport.create_time.between(start_at, end_at))
        rows = query.all()
        return [row[0] for row in rows]

    @classmethod
    async def delete_by_filters(cls, db: Session, cleanup_model: ReportDelModel) -> int:
        """
        根据报告ID、时间范围和用户ID清理测试报告。

        :param db: 数据库会话。
        :param cleanup_model: 清理参数模型。
        :return: 实际删除的报告数量。
        """
        report_ids = await run_in_threadpool(
            cls._collect_cleanup_report_ids_sync,
            db,
            cleanup_model.report_ids,
            cleanup_model.user_id,
            cleanup_model.begin_time,
            cleanup_model.end_time,
        )
        if not report_ids:
            return 0
        return await run_in_threadpool(cls._delete_sync, db, report_ids)

    @classmethod
    async def create(cls, db: Session, report_obj: ReportCreatModel) -> HrmReport:
        if report_obj.report_id:
            raise KeyError("参数异常")

        def _query(db: Session, report_obj: ReportCreatModel):
            report = HrmReport(**report_obj.model_dump(exclude_unset=True))
            db.add(report)
            db.commit()
            db.refresh(report)
            return report
        return await run_in_threadpool(_query, db, report_obj)



    @classmethod
    async def get_list(cls, db: Session, query_object: ReportQueryModel, data_scope_sql:DataScopeExpr):
        query = db.query(HrmReport).filter(data_scope_sql)
        if query_object.report_id:
            query = query.filter(HrmReport.report_id == query_object.report_id)
        if query_object.only_self:
            query = query.filter(HrmReport.manager == query_object.manager)

        if query_object.report_name:
            query = query.filter(HrmReport.report_name.like(f"%{query_object.report_name}%"))

        if query_object.status:
            query = query.filter(HrmReport.status == query_object.status)

        query = query.order_by(HrmReport.create_time.desc())

        result = await run_in_threadpool(PageUtil.paginate,
                                         query,
                                         query_object.page_num,
                                         query_object.page_size,
                                         query_object.is_page)

        result.rows = [ReportListModel.model_validate(row) for row in result.rows]
        return result
