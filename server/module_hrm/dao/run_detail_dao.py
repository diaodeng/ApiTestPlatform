from sqlalchemy.orm import Session
from datetime import datetime

from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, HrmRunListModel, HrmRunDetailModel
from utils.page_util import PageUtil
from utils.snowflake import snowIdWorker


class RunDetailDao:
    """
    报告数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, detail_id: int):
        data = db.query(HrmRunDetail).filter(HrmRunDetail.detail_id == detail_id).first()
        return data

    @classmethod
    def get_by_name(cls, db: Session, report_name: str):
        pass

    @classmethod
    def generate(cls, db: Session, report_name: str, report_content: str):
        pass

    @classmethod
    def update(cls, db: Session, report_id: int, report_name: str, report_content: str):
        pass

    @classmethod
    def delete(cls, db: Session, detail_ids: list):
        if detail_ids:
            db.query(HrmRunDetail).filter(HrmRunDetail.detail_id.in_(detail_ids)).delete()
            db.commit()

    @classmethod
    def create(cls, db: Session, run_id, report_id, run_type, run_name, run_start_time: datetime,
               run_end_time: datetime,
               run_duration: float = 0, run_detail: str = "", status: int = 1):
        """
        创建报告
        """
        duration = (run_end_time - run_start_time).microseconds / 1000000
        run_detail = HrmRunDetail(
            detail_id=snowIdWorker.get_id(),
            run_id=run_id,
            report_id=report_id,
            run_type=run_type,
            run_name=run_name,
            run_start_time=run_start_time,
            run_end_time=run_end_time,
            run_duration=duration,
            run_detail=run_detail,
            status=status
        )
        db.add(run_detail)
        db.commit()
        db.refresh(run_detail)
        return run_detail

    @classmethod
    def list(cls, db: Session, query_info: RunDetailQueryModel):
        query = db.query(HrmRunDetail)
        if query_info.run_id:
            query = query.filter(HrmRunDetail.run_id == query_info.run_id)
        if query_info.run_type:
            query = query.filter(HrmRunDetail.run_type == query_info.run_type)

        if query_info.status:
            query = query.filter(HrmRunDetail.status == query_info.status)

        if query_info.report_id:
            query = query.filter(HrmRunDetail.report_id == query_info.report_id)

        if query_info.run_name:
            query = query.filter(HrmRunDetail.run_name.like("%" + query_info.run_name + "%"))

        result = PageUtil.paginate(query, query_info.page_num, query_info.page_size, True)
        rows = []
        for row in result.rows:
            rows.append(HrmRunListModel.from_orm(row))

        result.rows = rows
        return result
