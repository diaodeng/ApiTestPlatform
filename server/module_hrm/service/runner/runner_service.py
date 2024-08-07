import json
import multiprocessing
import os
import platform
from collections import defaultdict

from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.do.suite_do import HrmSuite, HrmSuiteDetail
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo_detail_for_run import TestCaseSummary
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.service.runner.case_data_handler import CaseInfoHandle
from module_hrm.service.debugtalk_service import DebugTalkHandler, DebugTalkService
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.utils.util import compress_text
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from module_hrm.enums.enums import DataType
from sqlalchemy.orm import Session
from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao

logger.info(f"平台信息：{platform.platform()}")
if "WSL" in str(platform.platform()):
    multiprocessing.set_start_method("spawn")


async def run_by_single(query_db: Session, index, env_obj, func_map=None) -> list[TestCaseSummary]:
    test_case = CaseInfoHandle(query_db).from_db(index).toRun(env_obj).run_data()
    runner = TestRunner(test_case, func_map)
    case_res_datas = await runner.start()
    all_result = []
    for case_res_data in case_res_datas:
        all_result.append(case_res_data.result)

    return all_result


async def run_by_suite(query_db: Session, index, env, func_map=None):
    case_ids = query_db.query(HrmSuiteDetail.case_id).filter(HrmSuiteDetail.suite_id == index).distinct()
    include_case = list(case_ids)
    result = []
    for val in include_case:
        res_data = await run_by_single(query_db, val, env, func_map)
        result.extend(res_data)
    return result


async def run_by_batch(query_db: Session, test_list: list[int | str], env_id, type: int = None, mode=False,
                       user=None) -> list[TestCaseSummary]:
    """
    批量组装用例数据
    :param test_list:
    :param base_url: str: 环境地址
    :param type: str：用例级别
    :param mode: boolean：True 同步 False: 异步
    :return: list
    """

    project_cases = defaultdict(list)
    if type == DataType.project.value:
        for project_id in test_list:
            project_cases[project_id].append(project_id)
    elif type == DataType.module.value:
        all_module_obj = query_db.query(HrmModule.project_id, HrmModule.module_id).filter(
            HrmModule.module_id.in_(test_list)).all()
        for project_id, module_id in all_module_obj:
            project_cases[project_id].append(module_id)
    elif type == DataType.suite.value:
        project_case_ids = (query_db.query(HrmSuite.project_id, HrmSuiteDetail.case_id).
                            join(HrmSuiteDetail, HrmSuite.suite_id == HrmSuiteDetail.suite_id).
                            filter(HrmSuite.id.in_(test_list)).all())
        for project_id, case_id in project_case_ids:
            project_cases[project_id].append(case_id)
    else:
        project_case_ids = query_db.query(HrmCase.project_id, HrmCase.case_id).filter(
            HrmCase.case_id.in_(test_list)).all()
        for project_id, case_id in project_case_ids:
            project_cases[project_id].append(case_id)

    # project_ids = project_cases.keys()

    # init_data_handle(path, project_names)
    # debugtalk_source = DebugTalkService.debugtalk_source_for_caseid_or_projectid(query_db=query_db, project_ids=project_ids)
    # debugtalk_obj = DebugTalkHandler(debugtalk_source)
    # debugtalk_func_map = debugtalk_obj.func_map(user)

    env_data = CamelCaseUtil.transform_result(EnvDao.get_env_by_id(query_db, env_id))
    env_obj = EnvModel.from_orm(env_data)

    try:
        result = []
        for project_id, ids in project_cases.items():  # 按项目执行
            if not ids: continue
            commom_debugtalk, project_debugtalk = DebugTalkService.debugtalk_source_for_projectid(query_db, project_id)
            debugtalk_handler = DebugTalkHandler(project_debugtalk, commom_debugtalk)
            try:
                debugtalk_func_map = debugtalk_handler.func_map(user)
                for value in ids:
                    if type == DataType.project.value:
                        res_data = await run_by_project(query_db, value, env_obj, debugtalk_func_map)
                    elif type == DataType.module.value:
                        res_data = await run_by_module(query_db, value, env_obj, debugtalk_func_map)
                    # elif type == DataType.suite:
                    #     res_data = await run_by_suite(query_db, value, env_obj, debugtalk_func_map)
                    else:
                        res_data = await run_by_single(query_db, value, env_obj, debugtalk_func_map)
                    result.extend(res_data)
            finally:
                debugtalk_handler.del_import()
    finally:
        pass
        # debugtalk_obj.del_import()
    return result


async def run_by_module(query_db: Session, id, env, func_map=None):
    """
    组装模块用例
    :param id: int or str：模块索引
    :param env: str：环境ID
    :return: list
    """
    # obj = HrmModule.objects.get(id=id)
    test_index_list = query_db.query(HrmCase.case_id).filter(HrmCase.module_id == id).filter(
        HrmCase.type == DataType.case.value).distinct()
    result = []
    for index in test_index_list:
        res_data = await run_by_single(query_db, index[0], env, func_map)
        result.extend(res_data)
    return result


async def run_by_project(query_db: Session, id, env_obj, func_map=None):
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
        res_data = await run_by_module(query_db, module_id, env_obj, func_map)
        result.extend(res_data)
    return result


def get_report_content(report_path):
    if not report_path:
        return "请指定报告文件！"

    if not os.path.exists(report_path):
        return f"没有找到对应的测试报告：{report_path}"

    report_content = "未生成测试报告"
    with open(report_path, 'r', encoding="utf8") as rf:
        report_content = rf.read()

    return report_content
