import datetime

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportCreatModel, ReportListModel, ReportQueryModel
from module_hrm.enums.enums import CaseRunStatus
from module_admin.entity.vo.common_vo import DataScopeExpr
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
        duration = (datetime.datetime.now() - datetime.datetime.fromtimestamp(report.start_at.timestamp())).total_seconds()
        report.success = success
        report.total = total
        report.test_duration = duration
        report.status = status.value
        await run_in_threadpool(db.commit)

    @classmethod
    async def delete(cls, db: Session, report_ids: list):
        if report_ids:
            await run_in_threadpool(db.query(HrmReport).filter(HrmReport.report_id.in_(report_ids)).delete)
            await run_in_threadpool(db.commit)

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
