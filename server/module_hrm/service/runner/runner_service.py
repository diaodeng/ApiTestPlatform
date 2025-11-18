import asyncio
import gc
import multiprocessing
import os
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Type, AsyncGenerator

import httpx
from fastapi.concurrency import run_in_threadpool

from sqlalchemy.orm import Session

from config.database import SessionLocal
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.suite_do import QtrSuiteDetail, QtrSuite
from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.entity.vo.report_vo import ReportCreatModel
from module_hrm.entity.vo.run_detail_vo import HrmRunDetailModel
from module_hrm.enums.enums import DataType, CaseRunStatus, CaseStatusEnum, RunTypeEnum, QtrDataStatusEnum
from module_hrm.service.debugtalk_service import DebugTalkHandler, DebugTalkService
from module_hrm.service.runner.case_data_handler import CaseInfoHandle, ParametersHandler
from module_hrm.service.runner.case_runner import TestRunner
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.message_util import MessageHandler

logger.info(f"平台信息：{platform.platform()}")
if "WSL" in str(platform.platform()):
    multiprocessing.set_start_method("spawn")



def build_run_detail_info(case_data, run_info) -> HrmRunDetailModel|None:
    if case_data.case_id and isinstance(case_data.case_id, int):  # 没有ID的请求信息不记录
        # 保存前清空不必要的信息，减少数据存储
        case_data.config.variables = []
        case_data.config.headers = []
        # case_data.config.parameters = None

        for step in case_data.teststeps:
            step.variables = []

        run_detail_obj = HrmRunDetailModel()
        run_detail_obj.manager = run_info.runner
        run_detail_obj.run_id = case_data.case_id
        run_detail_obj.report_id = run_info.report_id
        run_detail_obj.run_type = run_info.run_type
        run_detail_obj.run_name = case_data.config.name
        run_detail_obj.run_start_time = datetime.fromtimestamp(case_data.config.result.start_time_stamp)
        run_detail_obj.run_end_time = datetime.fromtimestamp(case_data.config.result.end_time_stamp)
        logger.debug(f"用例{case_data.config.name}执行完成时间，stamp：{case_data.config.result.end_time_stamp}")
        logger.debug(f"用例{case_data.config.name}执行完成时间，format：{case_data.config.result.end_time_iso}")
        logger.debug(f"用例{case_data.config.name}执行完成时间，case 耗时：{case_data.config.result.duration}")
        run_detail_obj.run_duration = case_data.config.result.duration
        run_detail_obj.run_detail = case_data.model_dump_json(by_alias=True)
        run_detail_obj.status = case_data.config.result.status
        return run_detail_obj
    return None

async def save_run_detail(query_db, case_data, run_info):
    run_detail_obj = build_run_detail_info(case_data, run_info)
    if run_detail_obj:
        run_detail = RunDetailDao.create(query_db, run_detail_obj)
        return run_detail


async def run_by_single(case_data,
                        run_info: CaseRunModel = None,
                        semaphore: asyncio.Semaphore = None,
                        ) -> list[TestCase]:
    # test_case = CaseInfoHandle(query_db).from_db(index).toRun(env_obj).run_data()
    test_case = case_data
    case_res_datas = []
    if not test_case.status == CaseStatusEnum.normal.value:
        status = CaseRunStatus.xfailed
        if test_case.status == CaseStatusEnum.xfailed.value:
            status = CaseRunStatus.xfailed
        elif test_case.status == CaseStatusEnum.xpassed.value:
            status = CaseRunStatus.xpassed
        elif test_case.status == CaseStatusEnum.skipped.value:
            status = CaseRunStatus.skipped

        test_case.config.result.status = status.value
        test_case.config.result.success = True
        test_case.config.result.start_time_stamp = datetime.now().timestamp()
        test_case.config.result.end_time_stamp = datetime.now().timestamp()
        for step in test_case.teststeps:
            step.result.success = True
            step.result.status = status.value
            step.result.logs.before_request = f"用例状态为[{status.name}]不执行"
        case_res_datas = [test_case]
    else:
        async with semaphore:
            with SessionLocal() as db:
                debugtalk_info = await DebugTalkService.project_debugtalk_map(db, case_data.project_id, run_info=run_info)
            # func_map = debugtalk_info.func_map
            runner = TestRunner(test_case, debugtalk_info, run_info)
            case_res_datas = await runner.start()
    return case_res_datas

    # all_result = []
    # for case_res_data in case_res_datas:
        # all_result.append(case_res_data)
        # await save_run_detail(query_db, case_res_data, run_info)
        # await run_in_threadpool(save_run_detail, query_db, case_res_data, run_info)

    # return all_result


async def run_by_batch(run_info: CaseRunModel,
                       user=None
                       ) -> list[bool|int]:
    """
    批量组装用例数据
    :param test_list:
    :param base_url: str: 环境地址
    :param type: str：用例级别
    :param mode: boolean：True 同步 False: 异步
    :return: tuple[int, int, int]
    """

    async def get_case_data(query_db: Session, all_cases, data_type, ids: list):
        tmp_case_info_query = query_db.query(HrmCase.project_id, HrmCase.module_id,
                                             HrmCase.case_id).filter(
            HrmCase.status != CaseStatusEnum.disabled.value).filter(HrmCase.type == DataType.case.value)
        if data_type == RunTypeEnum.project.value:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.project_id.in_(ids))
        elif data_type == RunTypeEnum.model.value:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.module_id.in_(ids))
        else:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.case_id.in_(ids))
        tmp_case_info_query = await run_in_threadpool(tmp_case_info_query.all)
        for project_id, module_id, case_id in tmp_case_info_query:
            all_cases[project_id].append(case_id)

    success = True
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    all_cases = defaultdict(list)
    with SessionLocal() as query_db:
        if run_info.run_type == RunTypeEnum.suite.value:
            all_suite_orm = await run_in_threadpool(query_db.query(QtrSuite).filter(QtrSuite.suite_id.in_(run_info.ids)).order_by(
                QtrSuite.order_num).all)
            for suite_orm in all_suite_orm:
                if run_info.run_by_sort:
                    all_suite_content_orm = await run_in_threadpool(query_db.query(QtrSuiteDetail).
                                             filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                             filter(QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                             order_by(QtrSuiteDetail.order_num).all)
                    for suite_content_orm in all_suite_content_orm:
                        suite_data_id = suite_content_orm.data_id
                        data_type = suite_content_orm.data_type
                        await get_case_data(query_db, data_type, [suite_data_id])
                else:
                    all_case_item = await run_in_threadpool(query_db.query(QtrSuiteDetail.data_id).
                                     filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                     filter(QtrSuiteDetail.data_type == DataType.case.value).
                                     filter(QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                     order_by(QtrSuiteDetail.order_num).
                                     all)
                    await get_case_data(query_db, all_cases, RunTypeEnum.case.value, [case_item[0] for case_item in all_case_item])

                    all_not_case_item: list[Type[QtrSuiteDetail]] = await run_in_threadpool(query_db.query(QtrSuiteDetail).
                                                                     filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                                                     filter(
                        QtrSuiteDetail.data_type != DataType.case.value).
                                                                     filter(
                        QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                                                     order_by(QtrSuiteDetail.order_num).
                                                                     all)
                    for not_case_item in all_not_case_item:
                        run_type = RunTypeEnum.project.value if not_case_item.data_type == RunTypeEnum.project.value else RunTypeEnum.model.value

                        await get_case_data(query_db, all_cases, run_type, [not_case_item.data_id])
        else:
            await get_case_data(query_db, all_cases, run_info.run_type, run_info.ids)
        env_orm = await run_in_threadpool(EnvDao.get_env_by_id, query_db, run_info.env)
    env_data = CamelCaseUtil.transform_result(env_orm)
    env_obj = EnvModel.from_orm(env_data)

    try:
        limit = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        async with httpx.AsyncClient(limits=limit, http2=True) as client:
            run_info.http_client = client
            for project_id, ids in all_cases.items():  # 按项目执行
                if not ids: continue

                res_data = await run_by_concurrent(list(ids), env_obj, run_info)
                total_count += res_data[0]
                success_count += res_data[1]
                failed_count += res_data[2]
    except Exception as e:
        logger.error(f"运行用例失败，错误信息：{e}")
        logger.exception(e)
        success = False
        # ReportDao.update(query_db, run_info.report_id, 0, total_count, CaseRunStatus.failed)
        # raise e

    finally:
        for pdi in run_info.project_debugtalk_set.values():
            for mn in pdi.module_names:
                DebugTalkHandler.del_module(mn)
        gc.collect()
    return [success, total_count, success_count, failed_count]


async def get_case_info_batch(case_ids, env_obj) -> AsyncGenerator[TestCase, None]:
    all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
    # case_objs = CaseDao.get_case_by_ids(query_db, case_ids)
    async for case_obj in CaseDao.get_case_by_ids_iter(case_ids):
        with SessionLocal() as session:
            test_case = CaseInfoHandle(session).from_db(case_obj).toRun(env_obj).run_data()
        async for case_data in ParametersHandler.get_parameters_case([test_case]):
            yield case_data
        # all_data.extend(tmp_case_datas)
    # return all_data


async def run_by_concurrent(case_ids: list[int], env_obj,
                            run_info: CaseRunModel = None) -> list[int]:
    """
    并发执行多个用例
    """
    lock = asyncio.Lock()
    stats = {"total": 0, "success": 0, "failed": 0}
    queue = asyncio.Queue(maxsize=500)
    if run_info.run_by_sort:
        run_info.concurrent = 1
    semaphore = asyncio.Semaphore(run_info.concurrent)
    # case_data_list = get_case_info_batch(query_db, case_ids, env_obj)
    # case_data_group = [case_data_list[i:i + run_info.concurrent] for i in
    #                    range(0, len(case_data_list), run_info.concurrent)]

    async def worker(queue: asyncio.Queue, semaphore: asyncio.Semaphore, stats: dict, lock: asyncio.Lock):
        buffer = []
        batch_size = 50

        while True:
            case_data = await queue.get()
            if case_data is None:
                queue.task_done()
                break
            res_list = await run_by_single(case_data, run_info, semaphore)
            if not res_list:
                continue
            for res_data in res_list:
                async with lock:
                    data: TestCase = res_data
                    if data.config.result.status in [CaseRunStatus.passed.value, CaseRunStatus.skipped.value, CaseRunStatus.xpassed.value]:
                        stats["success"] += 1
                    elif data.config.result.status == CaseRunStatus.failed.value:
                        stats["failed"] += 1
                    stats["total"] += 1

                run_detail_obj = build_run_detail_info(data, run_info)
                if run_detail_obj:
                    buffer.append(run_detail_obj)

            if len(buffer) >= batch_size:
                async with lock:
                    with SessionLocal() as db:
                        await RunDetailDao.create_bulk(db, buffer)
                        await ReportDao.update(db, run_info.report_id, stats["success"], stats["total"], CaseRunStatus.running)
                buffer = []
            queue.task_done()


        if buffer:
            async with lock:
                with SessionLocal() as db:
                    await RunDetailDao.create_bulk(db, buffer)
                    await ReportDao.update(db, run_info.report_id, stats["success"], stats["total"], CaseRunStatus.running)

    tasks = [asyncio.create_task(worker(queue, semaphore, stats=stats, lock=lock)) for i in range(run_info.concurrent)]

    async for case_data in get_case_info_batch(case_ids, env_obj):
        await queue.put(case_data)

    await queue.join()

    for _ in range(len(tasks)):
        await queue.put(None)

    await asyncio.gather(*tasks)

    return [stats["total"], stats["success"], stats["failed"]]

async def run_test_in_background(run_info: CaseRunModel, current_user: CurrentUserModel):
    await run_by_async(run_info, current_user)
    logger.info(f"用例:{run_info.report_name}[{run_info.report_id}]执行完成")
    return "执行完成，请前往报告查看"



async def run_by_async(run_info: CaseRunModel,
                       current_user: CurrentUserModel,
                       ):
    """
    异步执行用例
    """
    test_start_time = time.time()
    start_time  =datetime.fromtimestamp(test_start_time, timezone.utc).astimezone(
            timezone(timedelta(hours=8)))
    report_id = None
    try:
        # query_db = SessionLocal()

        report_name = run_info.report_name or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_data = ReportCreatModel(**{"reportName": report_name,
                                          "status": CaseRunStatus.running.value,
                                          })
        logger.info(f"当前用户信息:{current_user.user.model_dump()}")
        report_data.update_by = current_user.user.user_name
        report_data.create_by = current_user.user.user_name
        report_data.manager = current_user.user.user_id
        report_data.dept_id = current_user.user.dept_id
        report_data.start_at = start_time
        with SessionLocal() as query_db:
            report_info = await ReportDao.create(query_db, report_data)
            run_info.report_id = report_info.report_id
            report_id = report_info.report_id

        success, total_count, success_count, failed_count = await run_by_batch(run_info,
                                        user=current_user.user.user_id)
        test_end_time = time.time()
        with SessionLocal() as query_db:
            report_info = await ReportDao.get_by_id(query_db, report_info.report_id)
            report_info.test_duration = test_end_time - test_start_time

            report_info.status = CaseRunStatus.failed.value if (not success or failed_count > 0 or total_count != success_count) else CaseRunStatus.passed.value
            report_info.total = total_count
            report_info.success = success_count
            await run_in_threadpool(query_db.commit)

        message_handler = MessageHandler(run_info)
        if message_handler.can_push():
            message_handler.feishu().push(
                f"[{current_user.user.user_name}]于{report_data.start_at}开始执行的测试完成。"
                f"\n总共：{total_count}条用例，成功：{success_count}条，失败：{total_count - success_count};"
                f"\n报告：【{run_info.report_id}】{report_name}")
        return f"执行成功，执行了{run_info.repeat_num}次，请前往报告查看"
    except Exception as e:
        logger.error(f"用例:{run_info.report_name}[{run_info.report_id}]执行失败，异常信息：{e}", exc_info=True)
        if report_id:
            with SessionLocal() as query_db:
                report_info = await ReportDao.get_by_id(query_db, report_id)
                report_info.test_duration = time.time() - test_start_time
                report_info.status = CaseRunStatus.failed.value
                await run_in_threadpool(query_db.commit)

        message_handler = MessageHandler(run_info)
        if message_handler.can_push():
            message_handler.feishu().push(
                f"[{current_user.user.user_name}]于{start_time}执行的测试失败。"
                f"\n异常信息：{e}")
    finally:
        pass
        # query_db.close()


def get_report_content(report_path):
    if not report_path:
        return "请指定报告文件！"

    if not os.path.exists(report_path):
        return f"没有找到对应的测试报告：{report_path}"

    report_content = "未生成测试报告"
    with open(report_path, 'r', encoding="utf8") as rf:
        report_content = rf.read()

    return report_content
