import copy
import json
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from module_hrm.dao.case_dao import CaseDao
from module_hrm.dao.env_dao import EnvDao
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import CaseModel, CaseRunModel
from module_hrm.entity.vo.case_vo_detail_for_handle import TestCase as TestCaseForHandle
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TStep
from module_hrm.entity.vo.env_vo import EnvModel, EnvModelForApi
from module_hrm.enums.enums import ParameterTypeEnum
from module_hrm.service.case_service import CaseParamsService
from module_hrm.utils.common import key_value_dict, dict2list, update_or_extend_list
from module_hrm.utils.parser import parse_data
from module_hrm.utils.util import decompress_text
from utils.log_util import logger
from utils.common_util import CamelCaseUtil
from module_hrm.service.agent_service import AgentService
from module_hrm.service.forward_rules_service import ForwardRulesService


class CaseInfoHandle():
    """
    用例、配置、API数据处理
    """

    def __init__(self, query_db: Session = None):
        self.query_db = query_db
        self.case_obj = None

    def __ensure_obj(self, case_obj):
        """

        """
        if not case_obj:
            return None
        if isinstance(case_obj, dict):
            case_obj = CaseModelForApi(**case_obj)
        elif isinstance(case_obj, (int, str)):
            case_orm = CaseDao.get_case_by_id(self.query_db, case_obj)
            case_obj = CaseModelForApi(**CamelCaseUtil.transform_result(case_orm))
        elif isinstance(case_obj, HrmCase):
            case_obj = CaseModelForApi(**CamelCaseUtil.transform_result(case_obj))
        elif not isinstance(case_obj, CaseModelForApi):
            case_obj = CaseModelForApi(**case_obj.dict())
        return case_obj

    def from_db(self, case_obj: CaseModel | CaseModelForApi | TestCase | dict | int | str):
        """
        处理数据库查出来的数据，用于运行、前端展示
        """

        self.case_obj = self.__ensure_obj(case_obj)
        return InToOut(self.query_db, self.case_obj)

    def from_db_run_detail(self, case_obj: TestCase | str):
        if isinstance(case_obj, str):
            case_obj = TestCase(**json.loads(case_obj))
        self.case_obj = CaseModelForApi()
        self.case_obj.case_id = case_obj.case_id
        self.case_obj.module_id = case_obj.module_id
        self.case_obj.project_id = case_obj.project_id
        self.case_obj.case_name = case_obj.config.name
        self.case_obj.request = case_obj
        return InToOut(self.query_db, self.case_obj)

    def from_page(self, case_obj: CaseModel | CaseModelForApi | dict | int | str):
        """
        处理前端来的数据，处理后用于运行、保存
        """
        self.case_obj = self.__ensure_obj(case_obj)
        return OutToIn(self.query_db, self.case_obj)


class OutToIn(object):
    def __init__(self, query_db: Session, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.case_data = case_obj

    def toDb(self):
        return CaseInfoToDb(self)

    def toDebug(self, env_obj: EnvModel | str | int):
        info_obj = CaseInfoToRun(self.query_db, env_obj=env_obj, case_obj=self.case_data)
        return info_obj


class InToOut(object):
    def __init__(self, query_db: Session, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.case_obj = case_obj

    def toPage(self):
        return CaseInfoToPage(self)

    def toRun(self, env_obj: EnvModel):
        return CaseInfoToRun(self.query_db, env_obj, self.case_obj)


class CaseInfoToPage(object):
    def __init__(self, data_obj: InToOut):
        self.case_obj = data_obj.case_obj

    def __dict_to_list(self, data: TestCase) -> CaseModelForApi:
        """
        字典转列表
        """
        test_case = data
        test_case_dict = data.model_dump(by_alias=True)
        test_case_dict["config"]["headers"] = dict2list(test_case.config.headers, True, )

        test_case_dict["config"]["variables"] = dict2list(test_case.config.variables, True)
        test_case_dict["config"]["parameters"] = dict2list(test_case.config.parameters)

        teststeps_list = []
        for teststep in test_case.teststeps:
            step_dict = teststep.model_dump(by_alias=True)
            step_dict["variables"] = dict2list(teststep.variables, True)
            step_dict["extract"] = dict2list(teststep.extract)

            step_dict["request"]["headers"] = dict2list(teststep.request.headers, True)
            step_dict["request"]["data"] = dict2list(teststep.request.data, True)
            step_dict["request"]["cookies"] = dict2list(teststep.request.cookies)
            step_dict["request"]["params"] = dict2list(teststep.request.params, True)
            teststeps_list.append(step_dict)
        test_case_dict["teststeps"] = teststeps_list
        # TestCase.validate(test_case_dict["request"])
        test_case_obj = TestCaseForHandle(**test_case_dict)
        data = {"projectId": test_case.project_id,
                "caseId": test_case.case_id,
                "moduleId": test_case.module_id,
                "request": test_case_obj.model_dump(by_alias=True)}
        case_data_obj = CaseModelForApi(**data)

        return case_data_obj

    def asApi(self) -> dict:
        return self.case_obj.model_dump(exclude_unset=True, by_alias=True)

    def asCase(self) -> CaseModelForApi:
        return self.case_obj

    def asConfig(self) -> dict:
        return self.asApi()


class CaseInfoToApi(object):
    def __init__(self, out_to_in: OutToIn):
        self._out_to_in = out_to_in
        step_length = len(self._out_to_in.case_data.get("request", {}).get("steps", []))
        if step_length > 1:
            raise AttributeError(
                f"api的步骤只能为1，{self._out_to_in.case_data.get('name', '')}:数据步骤太多（{step_length}）")
        self._api_data = self._out_to_in.case_data

    def data(self):
        return self._api_data


class CaseInfoToDb(object):
    def __init__(self, out_to_in: OutToIn):
        self.case_obj: CaseModelForApi = out_to_in.case_data

    def asCase(self) -> CaseModel:
        case_data = CaseModel(**self.case_obj.model_dump(by_alias=True))
        return case_data

    def asApi(self) -> CaseModel:
        return self.asCase()

    def asConfig(self) -> CaseModel:
        return self.asCase()


class CaseInfoToRun(object):
    def __init__(self, query_db: Session, env_obj: EnvModelForApi | EnvModel | str | int, case_obj: CaseModelForApi):
        self.query_db = query_db
        self.env_obj = self.__ensure_env_obj(env_obj)
        self.case_obj = case_obj

    def __ensure_env_obj(self, env) -> EnvModelForApi:
        if not env:
            raise AttributeError("请选择执行环境")
        if isinstance(env, (str, int)):
            env = EnvModelForApi(**CamelCaseUtil.transform_result(EnvDao.get_env_by_id(self.query_db, env)))
        elif isinstance(env, dict):
            env = EnvModelForApi(**env)
        elif not isinstance(env, EnvModelForApi):
            env = EnvModelForApi(**env.dict())
        return env

    def __include_handle(self) -> CaseModelForApi | None:
        """
        用例配置的include处理
        """
        include_config = self.case_obj.request.config.include.config
        test_include = None
        if include_config and hasattr(include_config, "id") and include_config.id and include_config.id != "":
            include_config = CaseDao.get_case_by_id(self.query_db, include_config.id)
            if include_config:
                test_include = CaseModelForApi(**CamelCaseUtil.transform_result(include_config))
        return test_include

    def __step_include_handle(self):
        """
        目前只处理了测试步骤配置的请求头
        """
        for step in self.case_obj.request.teststeps:
            if step.include.config and step.include.config.id:
                config_info = CaseDao.get_case_by_id(self.query_db, step.include.config.id)
                config_info = CaseModelForApi(**CamelCaseUtil.transform_result(config_info))
                config_header = copy.deepcopy(config_info.request.config.headers)
                update_or_extend_list(config_header, step.request.headers)
                step.request.headers = config_header

            config_headers = copy.deepcopy(self.case_obj.request.config.headers)
            config_headers = config_headers if config_headers else []
            if step.include.config.allow_extend:
                update_or_extend_list(config_headers, step.request.headers)
                step.request.headers = config_headers

    def __data_covert(self, data_obj: CaseModelForApi) -> TestCase:
        """
        将数据转换为测试用例的格式
        """
        # 处理数据
        test_case = data_obj
        test_case_dict = data_obj.model_dump(by_alias=True)
        test_case_dict["request"]["config"]["headers"] = key_value_dict(test_case.request.config.headers, True, True)

        test_case_dict["request"]["config"]["variables"] = key_value_dict(test_case.request.config.variables,
                                                                          checkEnable=True)
        test_case_dict["request"]["config"]["parameters"] = key_value_dict(test_case.request.config.parameters)

        teststeps_list = []
        for teststep in test_case.request.teststeps:
            step_dict = teststep.model_dump(by_alias=True)
            step_dict["variables"] = key_value_dict(teststep.variables, checkEnable=True)
            step_dict["extract"] = key_value_dict(teststep.extract)

            step_dict["request"]["headers"] = key_value_dict(teststep.request.headers, True, True)
            step_dict["request"]["data"] = key_value_dict(teststep.request.data, checkEnable=True)
            step_dict["request"]["cookies"] = key_value_dict(teststep.request.cookies)
            step_dict["request"]["params"] = key_value_dict(teststep.request.params, checkEnable=True)
            teststeps_list.append(step_dict)
        test_case_dict["request"]["teststeps"] = teststeps_list
        # TestCase.validate(test_case_dict["request"])
        test_case_obj = TestCase(**test_case_dict["request"])
        return test_case_obj

    def run_data(self) -> TestCase:
        """
        这里会创建目录和保存case数据为文件
        """
        # self._ensure_case_dir()

        env_varables = []
        # 获取环境变量
        for env_group in self.env_obj.env_config.variables:
            update_or_extend_list(env_varables, env_group.get("value", []))

        include_config_obj = self.__include_handle()

        self.case_obj.request.case_id = self.case_obj.case_id

        # 处理变量， 优先级： 环境变量 < include < case
        if include_config_obj:
            # 引用的配置中的变量
            update_or_extend_list(env_varables, include_config_obj.request.config.variables)

            # 用例其他配置处理：等待时间、请求超时时间
            if not self.case_obj.request.config.think_time.enable:
                if include_config_obj.request.config.think_time.enable:
                    self.case_obj.request.config.think_time = include_config_obj.request.config.think_time

            if not self.case_obj.request.config.time_out.enable:
                if include_config_obj.request.config.time_out.enable:
                    self.case_obj.request.config.time_out = include_config_obj.request.config.time_out
        # 用例配置中的变量
        update_or_extend_list(env_varables, self.case_obj.request.config.variables)

        # 配置请求头处理
        case_header = self.case_obj.request.config.headers
        include_header = include_config_obj.request.config.headers if include_config_obj else []
        include_header = copy.deepcopy(include_header)
        update_or_extend_list(include_header, case_header)
        self.case_obj.request.config.headers = include_header

        # 测试步骤请求头配置处理
        self.__step_include_handle()

        self.case_obj.request.config.variables = env_varables
        self.case_obj.request.project_id = self.case_obj.project_id
        self.case_obj.request.module_id = self.case_obj.module_id
        self.case_obj.request.case_id = self.case_obj.case_id
        self.case_obj.request.case_name = self.case_obj.case_name
        self.case_obj.request.status = self.case_obj.status

        return self.case_obj.request

    def debug_data(self) -> TestCase:
        """
        用测试用例入库的数据转成测试用的数据
        """
        return self.run_data()

    def case_data(self) -> TestCase:
        """
        这里只是处理数据，不会处理文件目录
        """
        return self.run_data()


class ParametersHandler(object):
    """
    参数处理器，用于处理参数化的情况
    """

    def __init__(self):
        pass

    @classmethod
    async def get_parameters(cls, query_db: Session, param_data) -> AsyncGenerator[dict|list[dict], None]:
        param_tmp_data = param_data
        param_index = 1
        if param_tmp_data.type == ParameterTypeEnum.local_table.value:
            parameter_source = decompress_text(param_tmp_data.value)
            parameter_obj = json.loads(parameter_source)
            # headers = parameter_obj.get("tableHeaders", [])
            datas = parameter_obj.get("tableDatas", [])

            for data in datas:
                # 只使用可用的数据
                enable = data.get("__enable", True)
                if not enable or not enable["content"]:
                    continue
                param = []
                for item in data:
                    # 排除状态字段
                    if item in ("__enable", "__row_key"):
                        continue
                    param.append({
                        "key": item,
                        "value": data[item].get("content", ""),
                        "enable": True,
                        "type": "string",
                    })
                param.append({
                    "key": "__index",
                    "value": param_index,
                    "enable": True,
                    "type": "int",
                })
                yield param
                param_index += 1
        elif param_tmp_data.type == ParameterTypeEnum.sql.value:
            async for data in CaseParamsService.load_case_params_iter(query_db, param_data.value):
                line_data = []
                for item in data:
                    if item in ("__enable", "__row_key"):
                        continue
                    line_data.append({
                        "key": item,
                        "value": data[item],
                        "enable": True,
                        "type": "string",
                        "index": param_index
                    })
                line_data.append({
                    "key": "__index",
                    "value": param_index,
                    "enable": True,
                    "type": "int",
                })
                yield line_data
                param_index += 1

    @classmethod
    async def get_parameters_case(cls, query_db: Session, case_datas: list[TestCase]) -> AsyncGenerator[TestCase, None]:
        """
        获取参数化之后的用例
        """
        # all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
        for test_case in case_datas:
            # test_case = CaseInfoHandle(query_db).from_db(case_id).toRun(env_obj).run_data()
            parameters = test_case.config.parameters
            if not parameters or (parameters.type == ParameterTypeEnum.local_table.value and not parameters.value):
                yield test_case
                continue

            if parameters.type == ParameterTypeEnum.sql.value:
                parameters.value = test_case.case_id

            async for param in cls.get_parameters(query_db, parameters):
                tmp_case_data = copy.deepcopy(test_case)
                old_variables: list[dict] = tmp_case_data.config.variables
                update_or_extend_list(old_variables, param)
                tmp_param = key_value_dict(param)
                # old_variables.update(param)
                tmp_case_data.config.variables = old_variables
                name = tmp_case_data.config.name or tmp_case_data.case_name
                if "case_name" in tmp_param:
                    tmp_case_data.config.name = f"{name}[{tmp_param['case_name']}]"
                    tmp_case_data.case_name = f"{name}[{tmp_param['case_name']}]"
                elif "caseName" in tmp_param:
                    tmp_case_data.config.name = f"{name}[{tmp_param['caseName']}]"
                    tmp_case_data.case_name = f"{name}[{tmp_param['caseName']}]"
                else:
                    tmp_case_data.config.name = f"{name}[{tmp_param['__index']}]"
                    tmp_case_data.case_name = f"{name}[{tmp_param['__index']}]"
                yield tmp_case_data
                # all_data.append(tmp_case_data)
        # return all_data


class ForwardRulesHandler(object):
    @classmethod
    def transform(cls, db, run_info: CaseRunModel):
        if run_info.forward_config.agent_id:
            run_info.forward_config.agent_code = AgentService.agent_detail_services(db,
                                                                                    run_info.forward_config.agent_id).agent_code
        if run_info.forward_config.forward_rule_ids:
            run_info.forward_config.forward_rules = ForwardRulesService.get_forward_rules_for_run(db,
                                                                                                  run_info.forward_config.forward_rule_ids)


class ConfigHandle:
    @classmethod
    def update_old_config_list(cls, old_config, new_config):
        if not isinstance(new_config, list):
            new_config = dict2list(new_config)
        update_or_extend_list(old_config, new_config)
        return old_config

    @classmethod
    def update_config_use_new_list(cls, new_config, old_config):
        if not isinstance(new_config, list):
            new_config = dict2list(new_config)
        update_or_extend_list(new_config, old_config)
        old_config = new_config
        return old_config

    @classmethod
    def parse_data_for_run(cls, data: str | dict, not_found_exception = True, debug_talk_map: dict = None, globals_var: dict | list = None, *args):
        if globals_var is None:
            globals_var = []
        if debug_talk_map is None:
            debug_talk_map = {}
        var_groups = args or []

        temp_all_val = copy.deepcopy(globals_var)
        if not isinstance(temp_all_val, list):
            temp_all_val = dict2list(temp_all_val)
        for var_group in var_groups:
            ConfigHandle.update_old_config_list(temp_all_val, var_group)

        temp_all_val_dict = key_value_dict(temp_all_val)
        new_data = parse_data(data,
                              temp_all_val_dict,
                              debug_talk_map,
                              not_found_exception
                              )
        return new_data


    @classmethod
    def can_run(cls, step_obj: TStep):
        can_run = True
        source_data = step_obj.run_condition.is_run_info.condition_source
        if step_obj.run_condition.is_run_info.enable and source_data:
            try:
                can_run = eval(source_data)
            except SyntaxError as se:
                can_run = False
                logger.error(f"步骤执行条件语法错误: {source_data}")
                # raise se
            except Exception as e:
                logger.error(f"步骤执行条件执行异常，判断条件: {source_data}，错误信息： {e}")
                can_run = False

        return can_run

    @classmethod
    def get_loop_info(cls, step_obj: TStep) -> tuple[str, list]:
        """
        获取测试步骤的循环条件信息
        """
        loop_num = 1
        if step_obj.run_condition.loop_run_info.enable:
            loop_num = step_obj.run_condition.loop_run_info.condition_source or 1

        loop_var = step_obj.run_condition.loop_run_info.loop_var or None
        return loop_var, [i for i in range(int(loop_num))]
