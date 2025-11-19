from sqlalchemy import select, func, case, literal
import datetime

from starlette.concurrency import run_in_threadpool

from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.do.run_detail_do import HrmRunDetail
from module_hrm.entity.do.suite_do import QtrSuite
from module_hrm.enums.enums import DataType, CaseRunStatus, RunTypeEnum
from module_hrm.service.case_service import Session


async def get_base_counts_subquery(query_db: Session):
    """使用子查询合并"""
    project_count = await run_in_threadpool(query_db.query(HrmProject).count)
    module_count = await run_in_threadpool(query_db.query(HrmModule).count)
    suite_count = await run_in_threadpool(query_db.query(QtrSuite).count)
    case_count = await run_in_threadpool(query_db.query(HrmCase).filter(HrmCase.type == DataType.case.value).count)

    return {
        'project': project_count,
        'module': module_count,
        'suite': suite_count,
        'case': case_count
    }

async def get_base_counts_optimized(query_db: Session):
    """基础统计"""
    # 使用select而不是query
    stmt = select(
        func.count(HrmProject.id).label('project'),
        func.count(HrmModule.id).label('module'),
        func.count(QtrSuite.id).label('suite'),
        func.count(HrmCase.id).filter(HrmCase.type == DataType.case.value).label('case')
    )

    result = await run_in_threadpool(query_db.execute(stmt).first)
    return {
        'project': result.project,
        'module': result.module,
        'suite': result.suite,
        'case': result.case
    }


async def get_base_counts(query_db: Session):
    """一次性获取所有基础统计"""
    from sqlalchemy import func

    # 使用子查询一次性获取所有计数
    project_subq = query_db.query(func.count(HrmProject.id)).scalar_subquery()
    module_subq = query_db.query(func.count(HrmModule.id)).scalar_subquery()
    suite_subq = query_db.query(func.count(QtrSuite.id)).scalar_subquery()
    case_subq = query_db.query(func.count(HrmCase.id)).filter(
        HrmCase.type == DataType.case.value
    ).scalar_subquery()

    # 单次查询获取所有结果
    result = await run_in_threadpool(query_db.query(project_subq, module_subq, suite_subq, case_subq).first)
    return result


async def get_run_statistics(query_db: Session):
    """运行统计"""
    from sqlalchemy import func, case

    today = datetime.date.today()
    start_date = today + datetime.timedelta(days=-11)
    end_date = today + datetime.timedelta(days=1)

    # 确保使用正确的过滤条件
    stats = query_db.query(
        func.date(HrmRunDetail.create_time).label('date'),
        func.count(HrmRunDetail.id).label('total_run'),
        func.sum(
            case(
                (HrmRunDetail.status == CaseRunStatus.passed.value, 1),
                else_=0
            )
        ).label('total_success')
    ).filter(
        HrmRunDetail.create_time >= start_date,
        HrmRunDetail.create_time < end_date,
        HrmRunDetail.run_type.in_([
            RunTypeEnum.case.value,
            RunTypeEnum.model.value,
            RunTypeEnum.suite.value,
            RunTypeEnum.project.value,
        ])
    ).group_by(
        func.date(HrmRunDetail.create_time)
    ).order_by(
        func.date(HrmRunDetail.create_time)
    )

    stats = await run_in_threadpool(stats.all)

    # 构建日期范围
    date_range = [today + datetime.timedelta(days=i) for i in range(-11, 1)]

    # 转换为字典
    stats_dict = {}
    for stat in stats:
        if stat.date:  # 确保日期不为空
            stats_dict[stat.date.strftime('%Y-%m-%d')] = stat

    # 构建返回数据
    total = {'pass': [], 'fail': [], 'percent': []}

    for current_date in date_range:
        date_str = current_date.strftime('%Y-%m-%d')
        stat = stats_dict.get(date_str)

        total_run = stat.total_run if stat else 0
        total_success = stat.total_success if stat else 0

        # 确保数值有效
        total_run = total_run or 0
        total_success = total_success or 0
        total_fail = total_run - total_success

        total_percent = round(total_success / total_run * 100, 2) if total_run > 0 else 0.00

        total['pass'].append(total_success)
        total['fail'].append(total_fail)
        total['percent'].append(total_percent)

    return total