import copy
import csv
import datetime
import io
import json
import os
import shutil
import subprocess
from json import JSONDecodeError

import yaml

from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TConfig, TStep
from module_hrm.enums.enums import CaseType, DataType
from module_hrm.exceptions import ParamsError
from module_hrm.utils import util
from utils.log_util import logger
from module_hrm.entity.vo.case_vo import CaseModel
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.env_vo import EnvModel
from module_hrm.utils.common import key_value_dict


class CaseInfoHandle():
    """
    用例、配置、API数据处理
    """

    def __init__(self, case_obj: CaseModel | CaseModelForApi | dict):
        self.case_obj = self.__ensure_obj(case_obj)

    def __ensure_obj(self, case_obj):
        """

        """
        if not isinstance(case_obj, CaseModelForApi):
            case_obj = CaseModelForApi(**case_obj)
        return case_obj

    def from_db(self, case_obj: CaseModel | CaseModelForApi | dict):
        """
        处理数据库查出来的数据，用于运行、前端展示
        """
        if case_obj:
            case_obj = self.__ensure_obj(case_obj)
        else:
            case_obj = self.case_obj
        return InToOut(case_obj)

    def from_page(self, case_obj: CaseModel | CaseModelForApi | dict):
        """
        处理前端来的数据，处理后用于运行、保存
        """
        if case_obj:
            case_obj = self.__ensure_obj(case_obj)
        else:
            case_obj = self.case_obj
        return OutToIn(case_obj)


class OutToIn(object):
    def __init__(self, case_obj: CaseModelForApi):
        self.case_data = case_obj

    def toDb(self):
        return CaseInfoToDb(self)

    def toDebug(self, env_obj: EnvModel):
        info_obj = CaseInfoToRun(env_obj=env_obj, case_obj=self.case_data)
        return info_obj


class InToOut(object):
    def __init__(self, case_obj: CaseModelForApi):
        self.case_obj = case_obj

    def toPage(self):
        return CaseInfoToPage(self)

    def toRun(self, env_obj: EnvModel):
        return CaseInfoToRun(env_obj, self.case_obj)


class CaseInfoToPage(object):
    def __init__(self, data_obj: InToOut):
        self.case_obj = data_obj.case_obj

    def asApi(self) -> dict:
        return self.case_obj.model_dump(exclude_unset=True, by_alias=True)

    def asCase(self) -> dict:
        return self.asApi()

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

    def asCase(self) -> dict:
        case_data = CaseModel(**self.case_obj)
        return case_data

    def asApi(self) -> dict:
        return self.asCase()

    def asConfig(self) -> dict:
        return self.asCase()


class CaseInfoToRun(object):
    def __init__(self, env_obj: EnvModel, case_obj: CaseModelForApi):

        self.env_obj = env_obj
        self.case_obj = case_obj

    def run_data(self, callback_func_map=None) -> TestCase:
        """
        这里会创建目录和保存case数据为文件
        """
        # self._ensure_case_dir()

        test_case = self.case_obj
        test_case_dict = self.case_obj.model_dump(exclude_unset=True, by_alias=True)
        test_case_dict["request"]["config"]["headers"] = key_value_dict(test_case.request.config.headers, True)
        test_case_dict["request"]["config"]["variables"] = key_value_dict(test_case.request.config.variables)
        test_case_dict["request"]["config"]["parameters"] = key_value_dict(test_case.request.config.parameters)

        teststeps_list = []
        for teststep in test_case.request.teststeps:
            step_dict = teststep.model_dump(exclude_unset=True, by_alias=True)
            step_dict["variables"] = key_value_dict(teststep.variables)
            step_dict["extract"] = key_value_dict(teststep.extract)

            step_dict["request"]["headers"] = key_value_dict(teststep.request.headers, True)
            step_dict["request"]["data"] = key_value_dict(teststep.request.data)
            step_dict["request"]["cookies"] = key_value_dict(teststep.request.cookies)
            step_dict["request"]["params"] = key_value_dict(teststep.request.params)
            teststeps_list.append(step_dict)
        test_case_dict["request"]["teststeps"] = teststeps_list
        CaseModelForApi.validate(test_case_dict)
        return TestCase(**test_case_dict["request"])

    def debug_data(self):
        """
        用测试用例入库的数据转成测试用的数据
        """
        case_name = self._case_data.get("name")
        include = self._case_data.get("include")
        request = self._case_data.get("request")
        return self._case_data_handle(case_name, include, request)

    def case_data(self) -> TestCase:
        """
        这里只是处理数据，不会处理文件目录
        """
        include = eval(self.case_obj.include or '[]')
        request = eval(self.case_obj.request)
        test_case = self._case_data_handle(self.case_obj.name, include, request)

        return test_case

    def parameter_handle(self, parameter: list):
        """
        返回元祖，第一个数字典类型的参数化内容（字典），一个是参数化用到的文件的路径（列表）
        """
        if not parameter:
            return {}, []
        new_parameter = {}
        parameter_file = []  # 参数化用到的文件路径
        for p in parameter:
            new_parameter[p['key']] = p.get("file_path")
            file_path = p.get("file_path")
            if file_path:  # 使用csv文件参数化的才需要这一步
                parameter_file.append(file_path)

        return new_parameter, parameter_file

    def update_config(self, old_config: dict, new_config: dict):
        """
        用新的配置更新老的配置，如果有相同字段会覆盖
        """
        headers = old_config.get("headers", {})
        headers.update(key_value_dict(new_config.pop("headers", {}), True))

        variables = old_config.get("variables", {})
        variables.update(key_value_dict(new_config.pop("variables", {})))

        environs = old_config.get("environs", {})
        environs.update(key_value_dict(new_config.pop("environs", {})))

        parameters = old_config.get("parameters", {})
        parameters.update(key_value_dict(new_config.pop("parameters", {})))

        websocket = old_config.get("websocket", {})
        websocket.update(key_value_dict(new_config.pop("websocket", {})))

        if headers:
            old_config["headers"] = headers

        if variables:
            old_config["variables"] = variables

        if environs:
            old_config["environs"] = environs

        if parameters:
            old_config["parameters"] = parameters

        if websocket:
            old_config["websocket"] = websocket

        old_config.update(new_config)

        return old_config

    def case_step_handle(self, case_name, case_request, case_config, is_include=False) -> list[TStep]:
        pre_request = case_request
        steps = []
        if "test" in pre_request:
            steps = [pre_request.get("test", {})]
        else:
            steps = pre_request.get('steps', [])
        for step in steps:
            if step['request']['url'] == "":
                raise TypeError(f"请求不能缺少URL：{case_name}")
            step.pop("step_id", "")
            all_new_valis = util.ensure_validate_v4(step.get('validate', []))
            step['validate'] = all_new_valis

            step["extract"] = key_value_dict(step.get("extract", []))
            step["variables"] = key_value_dict(step.get("variables", []))

            # 请求参数处理，这里可以不做处理，前端保存的时候数据已经处理了，只是为了兼容老数据
            if "data" in step.get('request').keys():
                data = step.get('request').pop('data', "")
                data_dict = key_value_dict('data', data)
                step.get('request').setdefault("data", data_dict)
            if "params" in step.get('request').keys():
                params = step.get('request').pop('params', "")
                data_dict = key_value_dict('data', params)
                step.get('request').setdefault("params", data_dict)

            #  headers处理
            pre_old_headers = step["request"].get("headers", {})
            step_include_config = step.get("include", {}).get("config", {})
            step_config_id = step_include_config.get("id")
            if step_config_id and step_config_id != "请选择":
                step_config_obj = TestCaseInfo.objects.get(id=step_config_id)
                step_config_headers = eval(step_config_obj.request).get("config", {}).get("headers", {})
                step_config_headers.update(pre_old_headers)
                pre_old_headers = step_config_headers

            # 没明白为什么config可以设置头，但是config设置了没在request中设置，执行用例时不会带上config中的
            # 所以这里手动赋值
            allow_extend = step_include_config.get("allowExtend", "1")
            if not step.get("include", {}):  # 老数据没有配置step的include，默认允许扩展
                allow_extend = "1"

            # 如果配置的允许扩展才将配置的请求头扩展到测试步骤的请求头中
            if allow_extend == "on" or allow_extend == "1":
                config_headers = copy.deepcopy(case_config.get("headers", {}))
                config_headers.update(pre_old_headers)
                pre_old_headers = config_headers
            step["request"]["headers"] = pre_old_headers

            # hooks处理
            setup_hooks = step.get("setup_hooks", [])
            setup_hooks.extend(case_config.get("setup_hooks", []))
            [st for st in setup_hooks if st.strip()]
            step["setup_hooks"] = setup_hooks

            teardown_hooks = step.get("teardown_hooks", [])
            teardown_hooks.extend(case_config.get("teardown_hooks", []))
            [st for st in teardown_hooks if st.strip()]
            step["teardown_hooks"] = teardown_hooks

            # parameters处理
            if is_include:
                # 引用的用例不能参数化，会影响当前用例本身
                logger.warning(f"引用的用例不能参数化，会影响当前用例本身:引用的用例名称：{case_name}")
                # raise TypeError("引用的用例不能参数化，会影响当前用例本身")
                # test_case['config']["parameters"] = list_dict_2_dict(params)
                # case_files.extend(pre_request["test"].pop("case_files", []))
            else:  # 老数据处理，新数据在步骤中不会有parameters，parameters在整个用例的config中
                params = step.pop("parameters", [])
                new_parameter, file_path = self.parameter_handle(params)
                self._case_files.extend(file_path)
                config_parameters = copy.deepcopy(case_config.get("parameters", {}))
                config_parameters.update(new_parameter)
                case_config["parameters"] = config_parameters

        return steps