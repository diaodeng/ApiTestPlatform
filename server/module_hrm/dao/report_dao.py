import datetime

from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportQueryModel, ReportListModel, ReportCreatModel
from module_hrm.enums.enums import CaseRunStatus
from utils.page_util import PageUtil


class ReportDao:
    """
    报告数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, report_id: int) -> HrmReport|None:
        return db.query(HrmReport).filter(HrmReport.report_id == report_id).first()

    @classmethod
    def get_by_name(cls, db: Session, report_name: str):
        pass

    @classmethod
    def generate_report(cls, db: Session, report_name: str, report_content: str):
        pass

    @classmethod
    def update(cls, db: Session, report_id: int, success: int, total: int, status: CaseRunStatus):
        report = cls.get_by_id(db, report_id)

        if not report:
            return
        duration = (datetime.datetime.now() - datetime.datetime.fromtimestamp(report.start_at.timestamp())).total_seconds()
        report.success = success
        report.total = total
        report.duration = duration
        report.status = status.value
        db.commit()

    @classmethod
    def delete(cls, db: Session, report_ids: list):
        if report_ids:
            db.query(HrmReport).filter(HrmReport.report_id.in_(report_ids)).delete()
            db.commit()

    @classmethod
    def create(cls, db: Session, report_obj: ReportCreatModel):
        if report_obj.report_id:
            raise KeyError("参数异常")

        report = HrmReport(**report_obj.model_dump(exclude_unset=True))
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @classmethod
    def get_list(cls, db: Session, query_object: ReportQueryModel, data_scope_sql:str):
        query = db.query(HrmReport).filter(eval(data_scope_sql))
        if query_object.only_self:
            query = query.filter(HrmReport.manager == query_object.manager)

        if query_object.report_name:
            query = query.filter(HrmReport.report_name.like(f"%{query_object.report_name}%"))

        if query_object.status:
            query = query.filter(HrmReport.status == query_object.status)

        query = query.order_by(HrmReport.create_time.desc())

        result = PageUtil.paginate(query, query_object.page_num, query_object.page_size, query_object.is_page)

        rows = []
        for row in result.rows:
            rows.append(ReportListModel.model_validate(row))

        result.rows = rows
        return result
