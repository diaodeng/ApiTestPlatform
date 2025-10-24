from sqlalchemy.orm import Session
from sqlalchemy import insert
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖
from starlette.concurrency import run_in_threadpool

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, HrmRunListModel, HrmRunDetailModel
from utils.page_util import PageUtil, PageResponseModel
from utils.log_util import logger


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
    async def create_bulk(cls, db: Session, details: list[HrmRunDetailModel]):
        """
        批量创建报告
        """

        detail_dicts = [detail.model_dump(exclude_unset=True) for detail in details]
        # run_details = [HrmRunDetail(**detail_dict) for detail_dict in detail_dicts]
        stmt = insert(HrmRunDetail).values(detail_dicts)
        await run_in_threadpool(db.execute, stmt)
        await run_in_threadpool(db.commit)

    @classmethod
    async def list(cls, db: Session, query_info: RunDetailQueryModel, data_scope_sql: str|None = None) -> PageResponseModel|list:
        logger.info(f"开始查询执行历史：{query_info.model_dump()}")
        query = db.query(HrmRunDetail)
        if query_info.report_id:
            query = query.filter(HrmRunDetail.report_id == query_info.report_id)

        if query_info.only_self:
            query = query.filter(HrmRunDetail.manager == query_info.manager)

        if query_info.status:
            query = query.filter(HrmRunDetail.status == query_info.status)

        if query_info.run_id:
            query = query.filter(HrmRunDetail.run_id == query_info.run_id)
        if query_info.run_type:
            query = query.filter(HrmRunDetail.run_type == query_info.run_type)


        if query_info.run_name:
            query = query.filter(HrmRunDetail.run_name.like("%" + query_info.run_name + "%"))
        if data_scope_sql:
            query = query.filter(eval(data_scope_sql))

        if query_info.report_id:
            query = query.order_by(HrmRunDetail.run_start_time, HrmRunDetail.run_end_time)
        elif query_info.run_id:
            query = query.order_by(HrmRunDetail.run_start_time.desc(), HrmRunDetail.run_end_time.desc())

        result = await run_in_threadpool(PageUtil.paginate, query, query_info.page_num, query_info.page_size, query_info.is_page)
        if not query_info.is_page:
            return result
        logger.info(f"执行历史查询结束")
        rows = []
        for row in result.rows:
            rows.append(HrmRunListModel.model_validate(row))

        result.rows = rows
        logger.info(f"执行历史数据组装完成: {len(result.rows)}")
        return result
