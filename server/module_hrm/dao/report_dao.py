from sqlalchemy.orm import Session

from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportQueryModel
from utils.page_util import PageUtil


class ReportDao:
    """
    报告数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, report_id: int):
        pass

    @classmethod
    def get_by_name(cls, db: Session, report_name: str):
        pass

    @classmethod
    def generate_report(cls, db: Session, report_name: str, report_content: str):
        pass

    @classmethod
    def update(cls, db: Session, report_id: int, report_name: str, report_content: str):
        pass

    @classmethod
    def delete(cls, db: Session, report_id: int):
        pass

    @classmethod
    def create(cls, db: Session, report_name: str, **kwargs):
        report = HrmReport(report_name=report_name, **kwargs)
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    @classmethod
    def get_list(cls, db: Session, query_object: ReportQueryModel):
        db.query(HrmReport).filter()
