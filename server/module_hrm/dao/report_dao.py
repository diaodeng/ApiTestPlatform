from sqlalchemy.orm import Session

from module_hrm.entity.do.report_do import HrmReport
from module_hrm.entity.vo.report_vo import ReportQueryModel, ReportListModel, ReportCreatModel
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
    def get_list(cls, db: Session, query_object: ReportQueryModel):
        query = db.query(HrmReport)
        if query_object.report_name:
            query = query.filter(HrmReport.report_name.like(f"%{query_object.report_name}%"))

        if query_object.status:
            query = query.filter(HrmReport.status == query_object.status)

        result = PageUtil.paginate(query, query_object.page_num, query_object.page_size, True)

        rows = []
        for row in result.rows:
            rows.append(ReportListModel.from_orm(row))

        result.rows = rows
        return result
