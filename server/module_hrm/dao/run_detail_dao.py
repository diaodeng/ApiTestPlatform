from typing import AsyncGenerator

from sqlalchemy.orm import Session, Query
from sqlalchemy import insert
from sqlalchemy.sql import or_, func  # 不能把删掉，数据权限sql依赖
from starlette.concurrency import run_in_threadpool

from module_admin.entity.do.dept_do import SysDept  # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept  # 不能把删掉，数据权限sql依赖

from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.vo.run_detail_vo import RunDetailQueryModel, HrmRunListModel, HrmRunDetailModel
from module_hrm.enums.enums import CaseRunStatus, RunTypeEnum
from module_hrm.utils.util import format_duration
from utils.common_util import CamelCaseUtil
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
    def _filter_handle(cls, query: Query[type[HrmRunDetail]], query_info: RunDetailQueryModel,
                       data_scope_sql: str | None = None):
        if query_info.report_id:
            query = query.filter(HrmRunDetail.report_id == query_info.report_id)

            if query_info.status:
                query = query.filter(HrmRunDetail.status == query_info.status)
            else:
                query = query.filter(HrmRunDetail.status.in_([e.value for e in CaseRunStatus]))

            query = query.order_by(HrmRunDetail.run_start_time, HrmRunDetail.run_end_time)

            if query_info.only_self:
                query = query.filter(HrmRunDetail.manager == query_info.manager)

            if query_info.run_id:
                query = query.filter(HrmRunDetail.run_id == query_info.run_id)

        elif query_info.run_id:
            query = query.filter(HrmRunDetail.run_id == query_info.run_id)

            if query_info.status:
                query = query.filter(HrmRunDetail.status == query_info.status)
            else:
                query = query.filter(HrmRunDetail.status.in_([e.value for e in CaseRunStatus]))

            if query_info.run_type:
                query = query.filter(HrmRunDetail.run_type == query_info.run_type)
            else:
                query = query.filter(HrmRunDetail.run_type.in_([e.value for e in RunTypeEnum]))
            query = query.order_by(HrmRunDetail.run_start_time.desc(), HrmRunDetail.run_end_time.desc())

            if query_info.only_self:
                query = query.filter(HrmRunDetail.manager == query_info.manager)

        if query_info.run_name:
            query = query.filter(HrmRunDetail.run_name.like("%" + query_info.run_name + "%"))
        if data_scope_sql:
            query = query.filter(eval(data_scope_sql))
        return query

    @classmethod
    async def list(cls, db: Session, query_info: RunDetailQueryModel,
                   data_scope_sql: str | None = None) -> PageResponseModel | list | None:
        logger.info(f"开始查询执行历史：{query_info.model_dump()}")
        if not query_info.report_id and not query_info.run_id:
            logger.error(f"查询执行历史参数异常")
            return None
        query = db.query(HrmRunDetail)
        query = cls._filter_handle(query, query_info, data_scope_sql)

        result = await run_in_threadpool(PageUtil.paginate, query, query_info.page_num, query_info.page_size,
                                         query_info.is_page)
        if not query_info.is_page:
            return result
        logger.info(f"执行历史查询结束")
        rows = []
        for row in result.rows:
            rows.append(HrmRunListModel.model_validate(row))

        result.rows = rows
        logger.info(f"执行历史数据组装完成: {len(result.rows)}")
        return result

    @classmethod
    async def list_iter(cls, db: Session,
                        query_info: RunDetailQueryModel,
                        data_scope_sql: str | None = None) -> AsyncGenerator[HrmRunDetail, None]:
        batch_size = 500
        offset = 0
        query = db.query(HrmRunDetail)

        query = cls._filter_handle(query, query_info, data_scope_sql)

        while True:
            query_result = await run_in_threadpool(query.offset(offset).limit(batch_size).all)
            if not query_result:
                break
            # for row in CamelCaseUtil.transform_result(query_result):
            for row in query_result:
                yield row  # 逐条 yield（或者改成 yield batch）
            offset += batch_size

    @classmethod
    async def get_report_count_info(cls, db: Session,
                                    query_info: RunDetailQueryModel,
                                    data_scope_sql: str | None = None) -> dict[str, int|str]:
        query = db.query(
            HrmRunDetail.status,
            func.count(HrmRunDetail.id).label('count'))
        query = cls._filter_handle(query, query_info, data_scope_sql)
        query = query.order_by(None)

        count_query_result = await run_in_threadpool(query.group_by(HrmRunDetail.status).all)



        count_result = {
            "success": 0,
            "successPercent": "0%",
            "fail": 0,
            "failPercent": "0%",
            "skip": 0,
            "skipPercent":"0%",
        }

        for status, count in count_query_result:
            run_status = status
            if run_status == CaseRunStatus.passed.value:
                count_result["success"] = count
            elif run_status == CaseRunStatus.failed.value:
                count_result["fail"] = count
            elif run_status == CaseRunStatus.skipped.value:
                count_result["skip"] = count
        total_count = count_result["success"] + count_result["fail"] + count_result["skip"]
        count_result["successPercent"] = f"{round(count_result["success"] / total_count * 100, 2)}%"
        count_result["failPercent"] = f"{round(count_result["fail"] / total_count * 100, 2)}%"
        count_result["skipPercent"] = f"{round(count_result["skip"] / total_count * 100, 2)}%"

        query = db.query(
            func.max(HrmRunDetail.run_duration).label('maxTime'),
            func.min(HrmRunDetail.run_duration).label('minTime'),
            func.avg(HrmRunDetail.run_duration).label('avgTime'),
            func.sum(HrmRunDetail.run_duration).label('totalTime'),
            func.count(HrmRunDetail.id).label('count')
        )
        query = cls._filter_handle(query, query_info, data_scope_sql)
        query = query.order_by(None)
        runtime_result = await run_in_threadpool(query.first)
        time_count = {
            'maxTime': format_duration(float(runtime_result.maxTime) if runtime_result.maxTime else 0),
            'minTime': format_duration(float(runtime_result.minTime) if runtime_result.minTime else 0),
            'avgTime': format_duration(float(runtime_result.avgTime) if runtime_result.avgTime else 0),
            'totalTime': format_duration(float(runtime_result.totalTime) if runtime_result.totalTime else 0),
            'count': format_duration(runtime_result.count)
        }
        count_result.update(time_count)
        return count_result
