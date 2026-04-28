from sqlalchemy import func, insert
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from module_hrm.entity.do.run_error_do import HrmRunError
from module_hrm.entity.vo.run_error_vo import (
    RunAssertReasonStatModel,
    RunErrorQueryModel,
    RunErrorRecordModel,
    RunErrorSummaryModel,
    RunErrorTypeStatModel,
)
from utils.page_util import PageResponseModel, PageUtil


class RunErrorDao:
    @classmethod
    async def create_bulk(cls, db: Session, errors: list[RunErrorRecordModel]):
        """
        批量写入执行错误事件，保证报告统计与执行详情同批落库。
        """
        if not errors:
            return

        error_dicts = [error.model_dump(exclude_unset=True, exclude_none=True) for error in errors]
        stmt = insert(HrmRunError).values(error_dicts)
        await run_in_threadpool(db.execute, stmt)

    @classmethod
    def delete_by_detail_ids(cls, db: Session, detail_ids: list[int]):
        """
        删除执行详情时同步清理关联错误事件，避免统计脏数据残留。
        """
        if not detail_ids:
            return
        db.query(HrmRunError).filter(HrmRunError.detail_id.in_(detail_ids)).delete(synchronize_session=False)

    @classmethod
    async def list(cls, db: Session, query_info: RunErrorQueryModel) -> PageResponseModel | list:
        """
        查询报告下的错误事件明细，支持按指纹和类型筛选。
        """
        query = db.query(HrmRunError)
        if query_info.report_id:
            query = query.filter(HrmRunError.report_id == query_info.report_id)
        if query_info.detail_id:
            query = query.filter(HrmRunError.detail_id == query_info.detail_id)
        if query_info.run_id:
            query = query.filter(HrmRunError.run_id == query_info.run_id)
        if query_info.error_type:
            query = query.filter(HrmRunError.error_type == query_info.error_type)
        if query_info.fingerprint:
            query = query.filter(HrmRunError.fingerprint == query_info.fingerprint)
        # if query_info.only_self:
        #     query = query.filter(HrmRunError.manager == query_info.manager)

        query = query.order_by(HrmRunError.create_time.desc(), HrmRunError.error_id.desc())
        result = await run_in_threadpool(
            PageUtil.paginate,
            query,
            query_info.page_num,
            query_info.page_size,
            query_info.is_page,
        )
        if not query_info.is_page:
            return result

        result.rows = [RunErrorRecordModel.model_validate(row) for row in result.rows]
        return result

    @classmethod
    async def get_summary_by_report(
        cls,
        db: Session,
        report_id: int,
        manager: int | None = None,
        only_self: bool = False,
    ) -> RunErrorSummaryModel:
        """
        聚合单次执行的错误类型分布和断言失败原因分布。
        """
        base_query = db.query(HrmRunError).filter(HrmRunError.report_id == report_id)
        if only_self and manager:
            base_query = base_query.filter(HrmRunError.manager == manager)

        total_count = await run_in_threadpool(base_query.count)
        assert_fail_count = await run_in_threadpool(
            base_query.filter(HrmRunError.error_type == 'assert_fail').count
        )
        exception_count = total_count - assert_fail_count

        type_rows = await run_in_threadpool(
            base_query.with_entities(
                HrmRunError.error_type,
                func.count(HrmRunError.error_id).label('count'),
            )
            .group_by(HrmRunError.error_type)
            .order_by(func.count(HrmRunError.error_id).desc())
            .all
        )

        assert_rows = await run_in_threadpool(
            base_query.with_entities(
                HrmRunError.fingerprint,
                HrmRunError.error_template,
                HrmRunError.error_subtype,
                HrmRunError.assert_name,
                HrmRunError.check_key,
                func.count(HrmRunError.error_id).label('count'),
                func.count(func.distinct(HrmRunError.detail_id)).label('case_count'),
            )
            .filter(HrmRunError.error_type == 'assert_fail')
            .group_by(
                HrmRunError.fingerprint,
                HrmRunError.error_template,
                HrmRunError.error_subtype,
                HrmRunError.assert_name,
                HrmRunError.check_key,
            )
            .order_by(func.count(HrmRunError.error_id).desc(), HrmRunError.error_template.asc())
            .all
        )

        return RunErrorSummaryModel(
            report_id=report_id,
            total_count=total_count,
            assert_fail_count=assert_fail_count,
            exception_count=exception_count,
            error_type_stats=[
                RunErrorTypeStatModel(error_type=row.error_type or '', count=int(row.count or 0))
                for row in type_rows
            ],
            assert_reason_stats=[
                RunAssertReasonStatModel(
                    fingerprint=row.fingerprint or '',
                    error_template=row.error_template or '',
                    error_subtype=row.error_subtype or '',
                    assert_name=row.assert_name or '',
                    check_key=row.check_key or '',
                    count=int(row.count or 0),
                    case_count=int(row.case_count or 0),
                )
                for row in assert_rows
            ],
        )
