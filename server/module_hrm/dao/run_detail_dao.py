from sqlalchemy.orm import Session
from datetime import datetime

from module_hrm.entity.do.run_detail_do import HrmRunDetail
from utils.page_util import PageUtil
from utils.snowflake import snowIdWorker


class RunDetailDao:
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
    def generate(cls, db: Session, report_name: str, report_content: str):
        pass

    @classmethod
    def update(cls, db: Session, report_id: int, report_name: str, report_content: str):
        pass

    @classmethod
    def delete(cls, db: Session, report_id: int):
        pass

    @classmethod
    def create(cls, db: Session, run_id, report_id, run_type, run_name, run_start_time: datetime, run_end_time: datetime,
               run_duration: float = 0, run_detail: str = "", status: int = 1):
        """
        创建报告
        """
        duration = (run_end_time - run_start_time).seconds
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
