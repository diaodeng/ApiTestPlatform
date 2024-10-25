from sqlalchemy.orm import Session

from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, HrmRunListModel, HrmRunDetailModel
from utils.page_util import PageUtil


class RunDetailDao:
    """
    报告数据库操作层
    """

    @classmethod
    def get_by_id(cls, db: Session, detail_id: int) -> HrmRunDetail:
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
    def create(cls, db: Session, detail: HrmRunDetailModel):
        """
        创建报告
        """
        # duration = (detail.run_end_time - detail.run_start_time).microseconds / 1000000
        # detail.run_duration = duration
        detail_dict = detail.model_dump(exclude_unset=True)
        run_detail = HrmRunDetail(**detail_dict)
        db.add(run_detail)
        db.commit()
        db.refresh(run_detail)
        return run_detail

    @classmethod
    def list(cls, db: Session, query_info: RunDetailQueryModel):
        query = db.query(HrmRunDetail)
        if query_info.only_self:
            query = query.filter(HrmRunDetail.manager == query_info.manager)
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

        query = query.order_by(HrmRunDetail.run_start_time.desc())

        result = PageUtil.paginate(query, query_info.page_num, query_info.page_size, True)
        rows = []
        for row in result.rows:
            rows.append(HrmRunListModel.from_orm(row))

        result.rows = rows
        return result
