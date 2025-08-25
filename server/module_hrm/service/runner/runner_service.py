import asyncio
import gc
import multiprocessing
import os
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Type

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
from module_message import MessageHandler

logger.info(f"平台信息：{platform.platform()}")
if "WSL" in str(platform.platform()):
    multiprocessing.set_start_method("spawn")


async def save_run_detail(query_db, case_data, run_info):
    if case_data.case_id and isinstance(case_data.case_id, int):  # 没有ID的请求信息不记录
        case_data.config.variables = []
        case_data.config.headers = []
        case_data.config.parameters = None

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

        run_detail = RunDetailDao.create(query_db, run_detail_obj)
        return run_detail


async def run_by_single(query_db: Session,
                        case_data,
                        env_obj,
                        func_map=None,
                        run_info: CaseRunModel = None) -> list[TestCase]:
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
        debugtalk_info = DebugTalkService.project_debugtalk_map(query_db, case_data.project_id, run_info=run_info)
        # func_map = debugtalk_info.func_map
        runner = TestRunner(test_case, debugtalk_info, run_info)
        case_res_datas = await runner.start()

    all_result = []
    for case_res_data in case_res_datas:
        all_result.append(case_res_data)
        await save_run_detail(query_db, case_res_data, run_info)

    return all_result


async def run_by_suite(query_db: Session, index, env, func_map=None):
    case_ids = query_db.query(QtrSuiteDetail.case_id).filter(QtrSuiteDetail.suite_id == index).distinct()
    include_case = list(case_ids)
    result = []
    for val in include_case:
        res_data = await run_by_single(query_db, val, env, func_map)
        result.extend(res_data)
    return result


async def run_by_batch(query_db: Session,
                       run_info: CaseRunModel,
                       user=None
                       ) -> list[TestCase]:
    """
    批量组装用例数据
    :param test_list:
    :param base_url: str: 环境地址
    :param type: str：用例级别
    :param mode: boolean：True 同步 False: 异步
    :return: list
    """

    def get_case_data(all_cases, data_type, ids: list):
        tmp_case_info_query = query_db.query(HrmCase.project_id, HrmCase.module_id,
                                             HrmCase.case_id).filter(
            HrmCase.status != CaseStatusEnum.disabled.value).filter(HrmCase.type == DataType.case.value)
        if data_type == RunTypeEnum.project.value:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.project_id.in_(ids))
        elif data_type == RunTypeEnum.model.value:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.module_id.in_(ids))
        else:
            tmp_case_info_query = tmp_case_info_query.filter(HrmCase.case_id.in_(ids))
        tmp_case_info_query = tmp_case_info_query.all()
        for project_id, module_id, case_id in tmp_case_info_query:
            all_cases[project_id].append(case_id)

    all_cases = defaultdict(list)
    if run_info.run_type == RunTypeEnum.suite.value:
        all_suite_orm = query_db.query(QtrSuite).filter(QtrSuite.suite_id.in_(run_info.ids)).order_by(
            QtrSuite.order_num).all()
        for suite_orm in all_suite_orm:
            if run_info.run_by_sort:
                all_suite_content_orm = (query_db.query(QtrSuiteDetail).
                                         filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                         filter(QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                         order_by(QtrSuiteDetail.order_num).all())
                for suite_content_orm in all_suite_content_orm:
                    suite_data_id = suite_content_orm.data_id
                    data_type = suite_content_orm.data_type
                    get_case_data(all_cases, data_type, [suite_data_id])
            else:
                all_case_item = (query_db.query(QtrSuiteDetail.data_id).
                                 filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                 filter(QtrSuiteDetail.data_type == DataType.case.value).
                                 filter(QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                 order_by(QtrSuiteDetail.order_num).
                                 all())
                get_case_data(all_cases, RunTypeEnum.case.value, [case_item[0] for case_item in all_case_item])

                all_not_case_item: list[Type[QtrSuiteDetail]] = (query_db.query(QtrSuiteDetail).
                                                                 filter(QtrSuiteDetail.suite_id == suite_orm.suite_id).
                                                                 filter(
                    QtrSuiteDetail.data_type != DataType.case.value).
                                                                 filter(
                    QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).
                                                                 order_by(QtrSuiteDetail.order_num).
                                                                 all())
                for not_case_item in all_not_case_item:
                    run_type = RunTypeEnum.project.value if not_case_item.data_type == RunTypeEnum.project.value else RunTypeEnum.model.value

                    get_case_data(all_cases, run_type, [not_case_item.data_id])
    else:
        get_case_data(all_cases, run_info.run_type, run_info.ids)

    env_data = CamelCaseUtil.transform_result(EnvDao.get_env_by_id(query_db, run_info.env))
    env_obj = EnvModel.from_orm(env_data)

    try:
        result = []
        debugtalk_func_map = None
        for project_id, ids in all_cases.items():  # 按项目执行
            if not ids: continue

            res_data = await run_by_concurrent(query_db, list(ids), env_obj, debugtalk_func_map, run_info)
            result.extend(res_data)

    finally:
        for pdi in run_info.project_debugtalk_set.values():
            for mn in pdi.module_names:
                DebugTalkHandler.del_module(mn)
        gc.collect()
    return result


def get_case_info_batch(query_db, case_ids, env_obj) -> list[TestCase]:
    all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
    case_objs = CaseDao.get_case_by_ids(query_db, case_ids)
    for case_obj in case_objs:
        logger.info(type(case_obj))
        test_case = CaseInfoHandle(query_db).from_db(case_obj).toRun(env_obj).run_data()
        tmp_case_datas = ParametersHandler.get_parameters_case([test_case])
        all_data.extend(tmp_case_datas)
    return all_data


def get_case_info(query_db, case_id, env_obj) -> list[TestCase]:
    case_obj = CaseDao.get_case_by_id(query_db, case_id)
    logger.info(type(case_obj))
    test_case = CaseInfoHandle(query_db).from_db(case_obj).toRun(env_obj).run_data()
    tmp_case_datas = ParametersHandler.get_parameters_case([test_case])
    return tmp_case_datas


async def run_by_module(query_db: Session, id, env, func_map=None, run_info: CaseRunModel = None):
    """
    组装模块用例
    :param id: int or str：模块索引
    :param env: str：环境ID
    :return: list
    """
    # obj = HrmModule.objects.get(id=id)
    test_index_list = query_db.query(HrmCase.case_id).filter(HrmCase.module_id == id).filter(
        HrmCase.type == DataType.case.value).filter(HrmCase.status != CaseStatusEnum.disabled.value).distinct()
    case_ids = [index[0] for index in test_index_list]
    result = await run_by_concurrent(query_db, case_ids, env, func_map, run_info)
    return result


async def run_by_project(query_db: Session, id, env_obj, func_map=None, run_info: CaseRunModel = None):
    """
    组装项目用例
    :param id: int or str：项目索引
    :param env: 环境对象
    :return: list
    """
    module_index_list = query_db.query(HrmModule.module_id).filter(HrmModule.project_id == id).order_by(
        HrmModule.sort).distinct()
    result = []
    for index in module_index_list:
        module_id = index[0]
        res_data = await run_by_module(query_db, module_id, env_obj, func_map, run_info)
        result.extend(res_data)
    return result


async def run_by_concurrent(query_db: Session, case_ids: list[int], env_obj, func_map=None,
                            run_info: CaseRunModel = None):
    """
    并发执行多个用例
    """
    case_data_list = get_case_info_batch(query_db, case_ids, env_obj)
    if not run_info.run_by_sort and run_info.concurrent > 1:
        # case_data_list = get_case_info_batch(query_db, case_ids, env_obj)
        case_data_group = [case_data_list[i:i + run_info.concurrent] for i in
                           range(0, len(case_data_list), run_info.concurrent)]

        results = []
        for case_datas in case_data_group:
            try:
                tasks = []
                for case_data in case_datas:
                    tasks.append(run_by_single(query_db, case_data, env_obj, func_map, run_info))
                result = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend([res for res_list in result for res in res_list])
            except Exception as e:
                logger.error(f"并发执行测试用例异常： {e}")
        return results
    else:
        result = []
        # for case_id in case_ids:
        #     case_datas = get_case_info(query_db, case_id, env_obj)
        for case_data in case_data_list:
            res_data = await run_by_single(query_db, case_data, env_obj, func_map, run_info)
            result.extend(res_data)
        return result


def test_run(run_info, current_user):
    query_db = SessionLocal()
    try:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        new_loop.run_until_complete(new_loop.create_task(run_by_async(query_db, run_info, current_user)))
        new_loop.close()

    finally:
        query_db.close()


async def run_by_async(query_db: Session, run_info: CaseRunModel,
                       current_user: CurrentUserModel,
                       ):
    """
    异步执行用例
    """
    try:
        # query_db = SessionLocal()
        test_start_time = time.time()
        report_name = run_info.report_name or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_data = ReportCreatModel(**{"reportName": report_name,
                                          "status": CaseRunStatus.passed.value,
                                          })
        logger.info(f"当前用户信息:{current_user.user.model_dump()}")
        report_data.update_by = current_user.user.user_name
        report_data.create_by = current_user.user.user_name
        report_data.manager = current_user.user.user_id
        report_data.dept_id = current_user.user.dept_id
        report_data.start_at = datetime.fromtimestamp(test_start_time, timezone.utc).astimezone(
            timezone(timedelta(hours=8)))
        report_info = ReportDao.create(query_db, report_data)
        query_db.commit()

        run_info.report_id = report_info.report_id

        run_result = await run_by_batch(query_db,
                                        run_info,
                                        user=current_user.user.user_id)
        test_end_time = time.time()

        report_info = ReportDao.get_by_id(query_db, report_info.report_id)
        report_info.test_duration = test_end_time - test_start_time
        report_status = report_info.status
        report_total = 0
        report_success = 0
        for case_data in run_result:
            report_total += 1
            if case_data.config.result.status == CaseRunStatus.failed.value:
                report_status = CaseRunStatus.failed.value
            elif case_data.config.result.status == CaseRunStatus.passed.value:
                report_success += 1

        report_info.status = report_status
        report_info.total = report_total
        report_info.success = report_success
        query_db.commit()

        message_handler = MessageHandler(run_info)
        if message_handler.can_push():
            message_handler.feishu().push(
                f"[{current_user.user.user_name}]于{report_info.start_at}开始执行的测试完成。"
                f"\n总共：{report_info.total}条用例，成功：{report_info.success}条，失败：{report_info.total - report_info.success};"
                f"\n报告：【{report_info.report_id}】{report_info.report_name}")
        return f"执行成功，执行了{run_info.repeat_num}次，请前往报告查看"
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
