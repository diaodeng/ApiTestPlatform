import json
import multiprocessing
import os
import platform

from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.do.suite_do import HrmSuite, HrmSuiteDetail
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.service.runner.case_data_handler import CaseInfoHandle
from module_hrm.service.debugtalk_service import DebugTalkHandler, DebugTalkService
from module_hrm.service.runner.case_runner import TestRunner
from module_hrm.utils.util import compress_text
from utils.log_util import logger
from module_hrm.enums.enums import DataType
from sqlalchemy.orm import Session
from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao

logger.info(f"平台信息：{platform.platform()}")
if "WSL" in str(platform.platform()):
    multiprocessing.set_start_method("spawn")


def run_by_single(query_db: Session, index, env_obj, func_map=None):
    case_data_obj = CaseDao.get_case_by_id(query_db, index)
    test_case = CaseInfoHandle().from_db(case_data_obj).toRun(env_obj).run_data(func_map)
    case_res_datas = TestRunner(test_case, func_map).start()
    all_result = []
    for case_res_data in case_res_datas:
        case_result_data = case_res_data.results
        case_res_data_json = {'status': case_res_data.status,
                              'steps': "",
                              'name': case_res_data.case_data.config.name,
                              'duration': case_res_data.duration,
                              "id": index
                              }
        steps_list = []
        for res in case_result_data:
            data = {"name": res.name,
                    "logs": res.logs,
                    'status': res.status,
                    "step_id": res.step_id,
                    "duration": res.duration
                    }
            steps_list.append(data)
        case_res_data_json['steps'] = compress_text(json.dumps(steps_list))
        all_result.append(case_res_data_json)

    return all_result


def run_by_suite(query_db: Session, index, env, func_map=None):
    case_ids = query_db.query(HrmSuiteDetail.case_id).filter(HrmSuiteDetail.suite_id == index).distinct()
    include_case = list(case_ids)
    result = []
    for val in include_case:
        res_data = run_by_single(val, env, func_map)
        result.extend(res_data)
    return result


def run_by_batch(query_db: Session, test_list: list[int | str], env_id, type: int=None, mode=False, user=None):
    """
    批量组装用例数据
    :param test_list:
    :param base_url: str: 环境地址
    :param type: str：用例级别
    :param mode: boolean：True 同步 False: 异步
    :return: list
    """
    project_ids = []
    if type == DataType.project:
        project_ids = test_list
    elif type == DataType.module:
        project_ids = query_db.query(HrmModule.project_id).filter(HrmModule.module_id.in_(test_list)).distinct()
    elif type == DataType.suite:
        suite_ids = query_db.query(HrmSuite.project_id).filter(HrmSuite.id.in_(test_list)).distinct()
        case_ids = query_db.query(HrmSuiteDetail.case_id).filter(HrmSuiteDetail.suite_id.in_(set(suite_ids))).distinct()
        include_case = list(case_ids)
        project_ids = query_db.query(HrmCase.project_id).filter(HrmCase.case_id.in_(include_case)).distinct()
    else:
        project_ids = query_db.query(HrmCase.project_id).filter(HrmCase.case_id.in_(test_list)).distinct()

    if project_ids:
        project_ids = list(set(project_ids))

    # init_data_handle(path, project_names)
    debugtalk_source = DebugTalkService.debugtalk_source_for_caseid_or_projectid(project_ids=project_ids)
    debugtalk_obj = DebugTalkHandler(debugtalk_source)
    debugtalk_func_map = debugtalk_obj.func_map(user)

    env_obj = EnvModel(**EnvDao.get_env_by_id(query_db, env_id))

    try:
        result = []
        for value in test_list:
            if type == DataType.project:
                res_data = run_by_project(query_db, value, env_obj, debugtalk_func_map)
            elif type == DataType.module:
                res_data = run_by_module(query_db, value, env_obj, debugtalk_func_map)
            elif type == DataType.suite:
                res_data = run_by_suite(query_db, value, env_obj, debugtalk_func_map)
            else:
                res_data = run_by_single(query_db, value, env_obj, debugtalk_func_map)
            result.extend(res_data)
    finally:
        debugtalk_obj.del_import()
    return result


def run_by_module(query_db: Session, id, env, func_map=None):
    """
    组装模块用例
    :param id: int or str：模块索引
    :param env: str：环境ID
    :return: list
    """
    # obj = HrmModule.objects.get(id=id)
    test_index_list = query_db.query(HrmCase.case_id).filter(HrmCase.module_id == id).distinct()
    result = []
    for index in test_index_list:
        res_data = run_by_single(query_db, index[0], env, func_map)
        result.extend(res_data)
    return result


def run_by_project(query_db: Session, id, env_obj, func_map=None):
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
        res_data = run_by_module(query_db, module_id, env_obj, func_map)
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
