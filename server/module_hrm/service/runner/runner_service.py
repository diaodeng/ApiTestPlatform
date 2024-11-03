import asyncio
import multiprocessing
import os
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from config.database import SessionLocal
from config.env import FeishuBotConfig
from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao
from module_hrm.dao.report_dao import ReportDao
from module_hrm.dao.run_detail_dao import RunDetailDao
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.suite_do import QtrSuiteDetail
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
from utils.message_util import FeiShuHandler, MessageHandler

logger.info(f"平台信息：{platform.platform()}")
if "WSL" in str(platform.platform()):
    multiprocessing.set_start_method("spawn")


async def save_run_detail(query_db, case_data, run_info):
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
        runner = TestRunner(test_case, func_map, run_info)
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
    project_cases = defaultdict(set)
    if run_info.run_type == RunTypeEnum.project.value:
        for project_id in run_info.ids:
            project_cases[project_id].add(project_id)
    elif run_info.run_type == RunTypeEnum.model.value:
        all_module_obj = query_db.query(HrmModule.project_id, HrmModule.module_id).filter(
            HrmModule.module_id.in_(run_info.ids)).all()
        for project_id, module_id in all_module_obj:
            project_cases[project_id].add(module_id)
    elif run_info.run_type == RunTypeEnum.suite.value:
        project_case_ids = (query_db.query(QtrSuiteDetail.data_id, QtrSuiteDetail.data_type).
                            filter(QtrSuiteDetail.suite_id.in_(run_info.ids)).filter(
            QtrSuiteDetail.status == QtrDataStatusEnum.normal.value).all())
        datas = defaultdict(set)
        for data_id, data_type in project_case_ids:
            datas[data_type].add(data_id)

        tmp_all_case = []
        for test_type in datas:
            if test_type == DataType.project.value:
                tmp_project_case = query_db.query(HrmCase.project_id, HrmCase.case_id).filter(
                    HrmCase.project_id.in_(datas[test_type])).filter(
                    HrmCase.status != CaseStatusEnum.disabled.value).all()
                tmp_all_case.extend(tmp_project_case)
            elif test_type == DataType.module.value:
                module_obj = query_db.query(HrmCase.project_id, HrmCase.case_id).filter(
                    HrmCase.module_id.in_(datas[test_type])).filter(
                    HrmCase.status != CaseStatusEnum.disabled.value).all()
                tmp_all_case.extend(module_obj)
            elif test_type == DataType.case.value:
                case_obj = query_db.query(HrmCase.project_id, HrmCase.case_id).filter(
                    HrmCase.case_id.in_(datas[test_type])).filter(HrmCase.status != CaseStatusEnum.disabled.value).all()
                tmp_all_case.extend(case_obj)
            for project_id, case_id in tmp_all_case:
                project_cases[project_id].add(case_id)
    else:
        project_case_ids = query_db.query(HrmCase.project_id, HrmCase.case_id).filter(
            HrmCase.case_id.in_(run_info.ids)).filter(HrmCase.status != CaseStatusEnum.disabled.value).all()
        for project_id, case_id in project_case_ids:
            project_cases[project_id].add(case_id)

    # project_ids = project_cases.keys()

    # init_data_handle(path, project_names)
    # debugtalk_source = DebugTalkService.debugtalk_source_for_caseid_or_projectid(query_db=query_db, project_ids=project_ids)
    # debugtalk_obj = DebugTalkHandler(debugtalk_source)
    # debugtalk_func_map = debugtalk_obj.func_map(user)

    env_data = CamelCaseUtil.transform_result(EnvDao.get_env_by_id(query_db, run_info.env))
    env_obj = EnvModel.from_orm(env_data)

    try:
        result = []
        for project_id, ids in project_cases.items():  # 按项目执行
            if not ids: continue
            commom_debugtalk, project_debugtalk = DebugTalkService.debugtalk_source(query_db, project_id=project_id)
            debugtalk_handler = DebugTalkHandler(project_debugtalk, commom_debugtalk)
            try:
                debugtalk_func_map = debugtalk_handler.func_map(user)
                if run_info.run_type not in [RunTypeEnum.project.value, RunTypeEnum.model.value]:  # 套件或者用例
                    res_data = await run_by_concurrent(query_db, list(ids), env_obj, debugtalk_func_map, run_info)
                    result.extend(res_data)
                else:  # 项目或者模块
                    for value in ids:
                        res_data = []
                        if run_info.run_type == RunTypeEnum.project.value:
                            res_data = await run_by_project(query_db, value, env_obj, debugtalk_func_map, run_info)
                        elif run_info.run_type == RunTypeEnum.model.value:
                            res_data = await run_by_module(query_db, value, env_obj, debugtalk_func_map, run_info)

                        result.extend(res_data)
            finally:
                debugtalk_handler.del_import()
    finally:
        pass
        # debugtalk_obj.del_import()
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
    module_index_list = query_db.query(HrmModule.module_id).filter(HrmModule.project_id == id).distinct()
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
    if run_info.concurrent > 1:
        case_data_group = [case_data_list[i:i + run_info.concurrent] for i in
                           range(0, len(case_data_list), run_info.concurrent)]
        tasks = []

        for case_datas in case_data_group:
            for case_data in case_datas:
                tasks.append(run_by_single(query_db, case_data, env_obj, func_map, run_info))
        result = await asyncio.gather(*tasks)
        return [res for res_list in result for res in res_list]
    else:
        result = []
        for case_data in case_data_list:
            res_data = await run_by_single(query_db, case_data, env_obj, func_map, run_info)
            result.extend(res_data)
        return result


async def run_by_async(query_db: Session, run_info: CaseRunModel,
                       current_user: CurrentUserModel,
                       ):
    """
    异步执行用例
    """
    # query_db = SessionLocal()
    try:
        test_start_time = time.time()
        report_name = run_info.report_name or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_data = ReportCreatModel(**{"reportName": report_name,
                                          "status": CaseRunStatus.passed.value,
                                          })
        report_data.update_by = current_user.user.user_name
        report_data.create_by = current_user.user.user_name
        report_data.manager = current_user.user.user_id
        report_info = ReportDao.create(query_db, report_data)
        report_info.start_at = datetime.fromtimestamp(test_start_time, timezone.utc).astimezone(
            timezone(timedelta(hours=8)))
        query_db.commit()

        run_info.report_id = report_info.report_id

        run_result = await run_by_batch(query_db,
                                        run_info,
                                        user=current_user.user.user_id)
        test_end_time = time.time()

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
