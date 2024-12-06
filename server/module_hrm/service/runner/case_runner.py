import asyncio
import copy
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Callable

import httpx
import jmespath
import requests
import urllib3
import websockets

from exceptions.exception import AgentForwardError
from module_hrm.entity.vo.case_vo import CaseRunModel, ForwardRulesForRunModel, ProjectDebugtalkInfoModel
from module_hrm.entity.vo.case_vo_detail_for_handle import ParameterModel, TStep as TStepForHandle, HooksModel, \
    CustomHooksParams, StepRunCondition
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TStep as TStepForRun, TRequest as TRequestForRun, \
    TWebsocket, ResponseData, \
    Result, StepLogs
from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum, ForwardRuleMatchTypeEnum, AgentResponseEnum, \
    CodeTypeEnum, ScopeEnum, AssertOriginalEnum, DataType
from module_hrm.exceptions import TestFailError
from module_hrm.service.runner.case_data_handler import ConfigHandle
from module_hrm.utils import comparators
from module_hrm.utils.CaseRunLogHandle import RunLogCaptureHandler, TestLog, CustomStackLevelLogger
from module_hrm.utils.case_run_utils import exec_js, exec_python
from module_hrm.utils import case_run_utils
from module_hrm.utils.common import key_value_dict, update_or_extend_list, dict2list, type_change
from module_hrm.utils.parser import parse_data, parse_function_set_default_params
from module_hrm.utils.util import replace_variables, compress_text
from module_qtr.service.agent_service import send_message, HandleResponse, AgentResponse, AgentResponseWebSocket
from utils.log_util import logger

# 忽略requests库https请求的警告
urllib3.disable_warnings()


class Response:
    def __init__(self, response_data: ResponseData, request: TRequestForRun | TWebsocket = None):
        self.status_code = response_data.status_code
        self.headers = response_data.headers
        self.content = response_data.content  # 响应内容为原始数据
        self.cookies = response_data.cookies
        self.request: TRequestForRun = request
        self.text: str = response_data.text
        self.body = response_data.body  # 默认不会有值，用于在回调中设置自己转换后的内容

    # @property
    # def text(self) -> str:
    #     """
    #     # 响应的原始数据转成text的结果
    #     """
    #     if isinstance(self.content, bytes):
    #         return self.content.decode('utf-8')
    #     elif isinstance(self.content, (dict, list, tuple)):
    #         return json.dumps(self.content, ensure_ascii=False)
    #     else:
    #         return self.content

    def json(self) -> dict | list:
        """
        响应数据装成json的结果，如果响应数据无法转成json且尝试调用json方法会抛出异常
        """
        try:
            new_data = []
            for i in json.loads(self.text):
                new_data.append(json.loads(i))
            return new_data
        except:
            return json.loads(self.text)

    # @property
    # def body(self) -> dict | str:
    #     try:
    #         return self.json()
    #     except:
    #         return self.text


class CaseRunUtil:
    @classmethod
    def exec_java_script(cls, js_source, run_info, case_data):
        exec_js()


class CaseRunner(object):
    def __init__(self, case_data: TestCase, debugtalk_func_map={}, logger: CustomStackLevelLogger = None,
                 run_info: CaseRunModel = None):

        self.case_data = case_data
        self.run_info = run_info
        self.logger = logger
        self.handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)

        self.debugtalk_func_map: dict = debugtalk_func_map  # 对应项目debugtalk方法
        # 全局变量中自身替换
        self.case_data.config.variables = self.__parse_in_case(self.case_data.config.variables)

    def __parse_in_case(self, data):
        return ConfigHandle.parse_data_for_run(data,
                                        self.debugtalk_func_map,
                                        self.run_info.global_vars,
                                        self.case_data.config.variables
                                        )

    def __exec_hook_script(self, hooks_info: HooksModel, is_before=True):
        """
        执行测试步骤中的自定义回调脚本
        """
        hooks_info.code_info.code_content = self.__parse_in_case(hooks_info.code_info.code_content)
        case_run_utils.exec_hook_script(hooks_info,
                                        self.logger,
                                        self.handler,
                                        self.case_data,
                                        self.run_info.global_vars,
                                        self.case_data.config.variables,
                                        None,
                                        is_before=is_before,
                                        data_type=DataType.case.value
                                        )

    def __sys_case_hook(self, hook_name: str):
        """
        测试步骤的系统回调
        """
        before_test = self.debugtalk_func_map.get(hook_name, None)
        if before_test:
            try:
                self.logger.info(f"开始处理{hook_name}")
                before_test(self.case_data)
                self.logger.info(f"{hook_name}处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            except Exception as e:
                self.logger.error(f"{hook_name}处理失败：{e}")
                self.logger.exception(e)
                self.case_data.config.result.status = CaseRunStatus.failed.value
                raise TestFailError(f"{hook_name}处理失败")

    def __custom_case_hook(self, hooks_info: HooksModel, hook_name: str = "case_setup", is_before=True):
        try:
            if hooks_info.functions:
                for setup_hook in hooks_info.functions:
                    hook = setup_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_data.config.variables)
                    parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.case_data,))
                    self.logger.info(f"{hook_name}处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            self.__exec_hook_script(hooks_info, is_before=is_before)
        except Exception as setupre:
            self.logger.error(f"{hook_name} error：{setupre}")
            self.logger.exception(setupre)
            self.case_data.config.result.status = CaseRunStatus.failed.value

    def __before_case(self):
        # 处理before_test, 执行开始测试之前的回调
        self.__sys_case_hook("before_case_test")

    def __case_setup(self):
        self.__custom_case_hook(self.case_data.config.setup_hooks)

    def __after_case(self):
        self.__sys_case_hook("after_case_test")

    def __case_teardown(self):
        self.__custom_case_hook(self.case_data.config.teardown_hooks, "case_teardown", is_before=False)

    def __close_handler(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
        del self.handler
        return self

    async def run(self):
        start_info = f"{'>>>开始执行用例：' + self.case_data.config.name:>^100}"
        # self.case_data.config.result = Result()
        setattr(self.case_data.config, "result", Result())
        self.logger.info(start_info)
        start_time = datetime.now(timezone.utc)
        self.case_data.config.result.start_time_stamp = start_time.timestamp()
        self.case_data.config.result.start_time_iso = start_time.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S")

        self.__before_case()
        self.__case_setup()

        self.case_data.teststeps = [step for step in self.case_data.teststeps if step.enable]
        new_steps = []
        for index, step in enumerate(self.case_data.teststeps):
            step_obj = None
            try:
                step_run_condition_dict = step.run_condition.model_dump(by_alias=True)
                new_data = ConfigHandle.parse_data_for_run(step_run_condition_dict,
                                                           self.debugtalk_func_map,
                                                           self.run_info.global_vars,
                                                           self.case_data.config.variables,
                                                           step.variables)
                step.run_condition = StepRunCondition(**new_data)

                loop_var, loop_list = ConfigHandle.get_loop_info(step)
                loop_num = len(loop_list)
                for loop_index, loop_value in enumerate(loop_list):
                    tmp_step = copy.deepcopy(step)
                    tmp_step.name = f"{tmp_step.name}[{loop_value}]" if loop_num > 1 else step.name
                    tmp_step.step_id = f"{tmp_step.step_id}{loop_index}" if loop_index > 0 else step.step_id
                    if loop_var:
                        tmp_step.variables.append({"key": loop_var, "value": loop_value, "enable": True})

                    if tmp_step.step_type == TstepTypeEnum.http.value:
                        step_obj = RequestRunner(self, tmp_step)
                    elif tmp_step.step_type == TstepTypeEnum.websocket.value:
                        step_obj = Websocket(self, tmp_step)
                    else:
                        self.logger.error(f"step type {tmp_step.step_type} not support")
                        raise TestFailError(f"step type {tmp_step.step_type} not support")

                    if ConfigHandle.can_run(tmp_step):
                        await step_obj.run()
                        step_obj = step_obj.validate()
                    else:
                        self.logger.info(f"跳过测试步骤【{tmp_step.name}】的执行")

                    # update_or_extend_list(self.case_data.config.variables, dict2list(step_obj.extract_variable))

                    log_content = self.handler.get_log()
                    step_obj.step_data.result.logs.after_response += log_content
                    step_data = step_obj.step_data

            except Exception as e:


                step_data = step_obj.step_data if step_obj else step

                if step_obj:
                    step_obj.set_step_failed()
                else:
                    self.case_data.config.result.status = CaseRunStatus.failed.value
                    self.case_data.config.result.success = False

                    if not step_data.result:
                        step_data.result = Result()
                    step_data.result.status = CaseRunStatus.failed.value
                    step_data.result.success = False

                    if not  step_data.result.logs:
                        step_data.result.logs = StepLogs()

                log_content = self.handler.get_log()
                step_data.result.logs.after_response += log_content

                self.logger.error(f"测试步骤【{step.name}】执行失败")
                self.logger.exception(e)
                step_data.result.logs.error += self.handler.get_log()

            finally:
                new_steps.append(step_data)

        self.case_data.teststeps = new_steps

        # del step_obj.debugtalk_func_map
        self.logger.info(f"{'执行结束用例：' + self.case_data.config.name + '<<<':<^100}")

        end_time = datetime.now(timezone.utc)
        self.logger.debug(f"用例{self.case_data.config.name}执行完成，耗时：{end_time - start_time}")
        self.logger.debug(
            f"用例{self.case_data.config.name}执行完成，耗时calc：{(end_time - start_time).total_seconds()}")
        self.case_data.config.result.end_time_stamp = end_time.timestamp()
        self.case_data.config.result.end_time_iso = end_time.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S")
        self.logger.debug(
            f"用例{self.case_data.config.name}执行完成时间，format：{self.case_data.config.result.end_time_iso}")
        self.case_data.config.result.duration = (end_time - start_time).total_seconds()

        self.__after_case()
        self.__case_teardown()

        for index, step_data in enumerate(self.case_data.teststeps):
            if index >= len(self.case_data.teststeps) - 1:
                log_content = self.handler.get_log()
                step_data.result.logs.after_response += log_content

            step_data.result.logs = compress_text(step_data.result.logs.model_dump_json())
            step_data.result.response = compress_text(
                step_data.result.response.model_dump_json())

        del self.debugtalk_func_map
        self.__close_handler()

        return self


class RequestConfig(object):
    def __init__(self, config_data):
        tem_config = json.dumps(config_data)
        tem_variables = config_data.get("variables", {})
        new_config = json.loads(replace_variables(tem_config, tem_variables))

        self.variables: dict = new_config.get("variables", {})
        self.base_url: str = new_config.get("base_url", None)
        self.case_name: str = new_config.get("name", "用例名")


class RequestRunner(object):
    def __init__(self, case_runner: CaseRunner, step_data: TStepForHandle):
        self.logger = case_runner.logger
        self.case_runner = case_runner
        self.debugtalk_func_map = case_runner.debugtalk_func_map
        self.step_data = step_data

        self.files = None
        self.response: Response = None
        self.extract_variable: dict = {}
        self.step_data.result = Result()

        self.teststep_other_config_handler()
        # self.parse_request_data()

    def format_time(self, start_time: int | float, end_time: int | float):
        self.step_data.result.duration = round(end_time - start_time, 2)
        self.step_data.result.start_time_stamp = start_time
        self.step_data.result.start_time_iso = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
        self.step_data.result.end_time_stamp = end_time
        self.step_data.result.end_time_iso = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
        self.logger.debug(f"用例{self.case_runner.case_data.config.name}执行完成时间，step耗时：{end_time - start_time}")
        self.logger.debug(
            f"用例{self.case_runner.case_data.config.name}执行完成时间，step format：{datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")

    def set_step_failed(self):
        logger.info(f"全局变量： {self.case_runner.run_info.global_vars}")
        logger.info(f"用例变量： {self.case_runner.case_data.config.variables}")
        logger.info(f"步骤变量： {self.step_data.variables}")
        self.step_data.result.status = CaseRunStatus.failed.value
        self.step_data.result.success = False
        self.case_runner.case_data.config.result.status = CaseRunStatus.failed.value
        self.case_runner.case_data.config.result.success = False

    def parse_data_in_step(self, data: str | dict):
        new_data = ConfigHandle.parse_data_for_run(data,
                                                   self.debugtalk_func_map,
                                                   self.case_runner.run_info.global_vars,
                                                   self.case_runner.case_data.config.variables,
                                                   self.step_data.variables
                                                   )
        return new_data

    def exec_hook_script(self, hooks_info: HooksModel, is_before=True):
        """
        执行测试步骤中的自定义回调脚本
        """
        case_run_utils.exec_hook_script(hooks_info,
                                        self.logger,
                                        self.case_runner.handler,
                                        self.step_data,
                                        self.case_runner.run_info.global_vars,
                                        self.case_runner.case_data.config.variables,
                                        self.step_data.result.logs,
                                        is_before=is_before,
                                        data_type="step"
                                        )

    def sys_step_hook(self, hook_name: str, log_store: StepLogs, is_after_step: bool = False):
        """
        测试步骤的系统回调
        """
        before_teststep: Callable = self.debugtalk_func_map.get(hook_name, None)
        if before_teststep:
            try:
                before_teststep(self.step_data)
                # self.parse_data_in_step(self.step_data)
                self.logger.info(f"系统{hook_name}回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            except Exception as e:
                if is_after_step:
                    log_store.after_response += self.case_runner.handler.get_log()
                else:
                    log_store.before_request += self.case_runner.handler.get_log()
                raise TestFailError(f"{hook_name}函数执行失败: {e}") from e

    def custom_step_hook(self,
                         hooks_info: HooksModel,
                         log_store: StepLogs,
                         hook_name: str = "test_step_setup",
                         is_after_step: bool = False):

        try:
            if hooks_info.functions:
                for teardown_hook in hooks_info.functions:
                    hook = teardown_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_runner.case_data.config.variables)
                    parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.step_data,))
                    self.logger.info(
                        f"自定义{hook_name}回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            hooks_info.code_info.code_content = self.parse_data_in_step(hooks_info.code_info.code_content)
            self.exec_hook_script(hooks_info, is_before=not is_after_step)
        except Exception as setupre:
            if is_after_step:
                log_store.after_response += self.case_runner.handler.get_log()
            else:
                log_store.before_request += self.case_runner.handler.get_log()
            raise TestFailError(f"{hook_name} error：{setupre}") from setupre

    def parse_request_data(self):
        self.logger.info("开始替换请求信息中的变量")
        step_data = self.step_data.model_dump(by_alias=True)
        request_data = step_data["request"]

        request_data = self.parse_data_in_step(request_data)

        try:
            if not urllib.parse.urlparse(request_data["url"]).scheme:
                request_data["url"] = urllib.parse.urljoin(self.case_runner.case_data.config.base_url,
                                                           request_data["url"])
        except:
            request_data["url"] = urllib.parse.urljoin(self.case_runner.case_data.config.base_url, request_data["url"])

        step_data["request"] = request_data
        self.step_data = TStepForRun(**step_data)  # 这里转换了请求数据格式

        if self.step_data.step_type == TstepTypeEnum.http.value:  ## http请求才会有json参数
            # 处理json变量，如果整体都是变量直接替换后再json.loads会报错
            old_json = self.step_data.request.req_json
            if old_json and isinstance(old_json, str):
                self.step_data.request.req_json = json.loads(old_json)
        self.logger.info("替换请求信息中的变量替换完成")

    def before_teststep_handler(self):
        # 请求前的回调
        self.sys_step_hook("before_test_step", self.step_data.result.logs.before_request)

    def after_teststep_handler(self):
        # 响应回调
        self.sys_step_hook("after_test_step",
                           self.step_data.result.logs.after_response,
                           is_after_step=True)

    def teststep_setup_handler(self):
        self.custom_step_hook(self.step_data.setup_hooks,
                              self.step_data.result.logs)

    def teststep_tearndown_handler(self):
        self.custom_step_hook(self.step_data.teardown_hooks,
                              self.step_data.result.logs,
                              "test_step_tearndown",
                              is_after_step=True)

    def teststep_other_config_handler(self):
        # 其他配置（超时时间、思考时间、重试次数）处理
        if not self.step_data.think_time.enable:
            self.step_data.think_time = self.case_runner.case_data.config.think_time

        if not self.step_data.time_out.enable:
            self.step_data.time_out = self.case_runner.case_data.config.time_out

        if not self.step_data.retry.enable:
            self.step_data.retry = self.case_runner.case_data.config.retry

        if self.step_data.time_out.enable:
            self.step_data.request.timeout = self.step_data.time_out.limit
        else:
            self.step_data.request.timeout = None

    def get_forward_url(self, forward_rules: list):
        """
        根据不同的转发规则判断是否需要转发，并返回对应的url
        """
        run_info = self.case_runner.run_info
        old_url = self.step_data.request.url
        if not run_info.forward_config.forward: return old_url
        for rule in forward_rules:

            new_url = rule.origin_url
            match_type = rule.match_type
            matched = False
            if match_type == ForwardRuleMatchTypeEnum.url_equal.value:
                matched = old_url == new_url
            elif match_type == ForwardRuleMatchTypeEnum.url_not_equal.value:
                matched = old_url != new_url
            elif match_type == ForwardRuleMatchTypeEnum.url_contain.value:
                matched = new_url in old_url
            elif match_type == ForwardRuleMatchTypeEnum.host_equal.value:
                matched = urllib.parse.urlparse(old_url).hostname == urllib.parse.urlparse(new_url).hostname
            elif match_type == ForwardRuleMatchTypeEnum.host_not_equal.value:
                matched = urllib.parse.urlparse(old_url).hostname != urllib.parse.urlparse(new_url).hostname
            elif match_type == ForwardRuleMatchTypeEnum.host_contain.value:
                matched = urllib.parse.urlparse(new_url).hostname in urllib.parse.urlparse(old_url).hostname
            elif match_type == ForwardRuleMatchTypeEnum.path_equal.value:
                matched = urllib.parse.urlparse(old_url).path == urllib.parse.urlparse(new_url).path
            elif match_type == ForwardRuleMatchTypeEnum.path_not_equal.value:
                matched = urllib.parse.urlparse(old_url).path != urllib.parse.urlparse(new_url).path
            elif match_type == ForwardRuleMatchTypeEnum.path_contain.value:
                matched = urllib.parse.urlparse(new_url).path in urllib.parse.urlparse(old_url).path

            if matched:
                return rule.target_url

        return old_url

    async def run(self):
        """
        执行统一调用这个方法
        """
        try:
            self.parse_request_data()

            # 系统回调
            self.before_teststep_handler()

            # 自定义回调
            self.teststep_setup_handler()

            self.logger.info(f'{">>>请求:" + self.step_data.name:=^100}')
            self.logger.info(f"原url: {self.step_data.request.url}")

            await self.request()

            self.after_teststep_handler()

            self.teststep_tearndown_handler()

            self.response = Response(self.step_data.result.response, self.step_data.request)

            self.step_data.result.response.body = self.response.body

            self.extract_data()

            self.step_data = TStepForHandle(**self.step_data.model_dump(by_alias=True))  ## 数据转回原来的格式
            return self
        except Exception as e:
            self.step_data.result.logs.after_response += self.case_runner.handler.get_log()
            raise TestFailError(f"测试步骤【{self.step_data.name}】异常了： {e}") from e
        # finally:
        #     return self

    def handler_forward_url(self, request_data: dict):
        """
        处理转发URL
        """
        if self.case_runner.run_info.forward_config.forward:
            old_rules = self.case_runner.run_info.forward_config.forward_rules
            old_rules_dict = [old_rule.model_dump(by_alias=True) for old_rule in old_rules]
            old_rules_str = json.dumps(old_rules_dict, ensure_ascii=False)
            parsed_rules_str = self.parse_data_in_step(old_rules_str)
            parsed_rules_dict = json.loads(parsed_rules_str)
            new_rules = [ForwardRulesForRunModel(**parsed_rule_dict) for parsed_rule_dict in parsed_rules_dict]
            new_url = self.get_forward_url(new_rules)
            request_data["url"] = new_url
            self.logger.info(f"需要转发， 转发规则：{parsed_rules_dict}")
            self.logger.info(f"需要转发， 转发地址：{new_url}")

    async def request(self):
        """
        不同的请求类型自行重写这个方法
        """

        request_data = self.step_data.request.model_dump(by_alias=True)

        self.logger.info(f"method: {self.step_data.request.method}")
        self.logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")

        try:
            self.step_data.result.logs.before_request += self.case_runner.handler.get_log()
            request_data.pop("dataType", None)
            request_data.pop("upload")
            request_data["follow_redirects"] = request_data.pop("allow_redirects", True)
            request_data.pop("verify", True)

            start_time = time.time()
            start_request_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            self.logger.debug(
                f"发起请求，请求时间:{start_request_time} >> {self.case_runner.case_data.config.name}")

            self.handler_forward_url(request_data)

            res_response: AgentResponse | httpx.Response = None

            if self.case_runner.run_info.forward_config.forward and self.case_runner.run_info.forward_config.agent_code:
                self.logger.info(f"通过调用客户机转发， 客户机：{self.case_runner.run_info.forward_config.agent_code}")
                request_data["requestType"] = self.step_data.step_type
                agent_res_obj: HandleResponse = await send_message(self.case_runner.run_info.forward_config.agent_code,
                                                                   request_data
                                                                   )
                if agent_res_obj.status_code != AgentResponseEnum.SUCCESS.value:
                    raise AgentForwardError("", f"客户机异常： {agent_res_obj.message}")

                res_response: AgentResponse = agent_res_obj.response

            else:
                async with httpx.AsyncClient() as client:
                    res_response = await client.request(**request_data)

            self.logger.debug(f"请求响应结果：{res_response}")
            self.logger.debug(f"请求总耗时时间：{res_response.elapsed.total_seconds()}")
            self.logger.debug(
                f"请求完成，完成时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')} >> {self.case_runner.case_data.config.name}")

            end_time = time.time()
            self.format_time(start_time, end_time)

            if self.step_data.think_time.limit:
                await asyncio.sleep(self.step_data.think_time.limit)

            self.logger.info(f'{"<<<请求结束:" + self.step_data.name:=^100}')
            self.logger.info(f'实际请求Url: {res_response.request.url}')
            self.logger.info(f'status_code: {res_response.status_code}')
            self.logger.info(
                f'response.headers: {json.dumps(dict(res_response.headers), indent=4, ensure_ascii=False)}')
            self.logger.info(f'response.text: {res_response.text}')

            res_obj = ResponseData()
            res_obj.text = res_response.text
            res_obj.content = res_response.content.decode("utf8")
            res_obj.status_code = res_response.status_code
            res_obj.headers = dict(res_response.headers)
            res_obj.cookies = dict(res_response.cookies)
            self.step_data.result.response = res_obj
            # self.response = Response(res_obj, self.step_data.request)
        except Exception as e:
            self.logger.exception(e)
            msg = str(e)
            if not isinstance(e, requests.exceptions.RequestException):
                msg = f"请求异常：{msg}"

            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": msg}, indent=4, ensure_ascii=False)}')
            self.response = None
            self.set_step_failed()
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.before_request += error_info
            self.step_data.result.logs.error += error_info
            return self
        return self

    def extract_data(self):
        """
        从请求响应中提取变量
        """
        self.logger.info(f"{self.step_data.name} 开始提取变量")
        try:
            for index, item in enumerate(self.step_data.extract):
                if not item.get("enable", True): continue
                val = self.__get_validate_key(item["value"])
                self.extract_variable[item["key"]] = val

                if item.get("scope", ScopeEnum.case.value) == ScopeEnum.case.value:
                    update_or_extend_list(self.case_runner.case_data.config.variables, dict2list(self.extract_variable))
                elif item.get("scope") == ScopeEnum.globals.value:
                    self.case_runner.run_info.global_vars.update(self.extract_variable)

            self.logger.info(f'{self.step_data.name} extract_variable: {json.dumps(self.extract_variable)}')
            self.logger.info(f"{self.step_data.name} 变量提取完成")

            return self
        except Exception as e:
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info

            self.set_step_failed()
            self.logger.error(f'{self.step_data.name} 提取变量失败\n {e}')
            self.logger.exception(e)

            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info
            self.step_data.result.logs.error += error_info

    def validate(self):
        try:
            if not self.step_data.result.success: return self
            # 校验数据处理回调
            self.logger.info(f"{self.step_data.name} 开始校验")
            before_request_validate = self.debugtalk_func_map.get("before_request_validate", None)
            if before_request_validate:
                before_request_validate(self.step_data.validators)

            for vali in self.step_data.validators:
                if not vali.get("enable", True): continue

                assert_key = vali["assert"]
                assert_key = self.parse_data_in_step(assert_key)
                check_key = vali["check"]
                check_key: str = self.parse_data_in_step(check_key)
                vali["check"] = check_key

                expect = vali["expect"]
                expect = self.parse_data_in_step(expect)
                vali["expect"] = expect  # 类型便更之前保存数据，为了原样保存
                expect = type_change(vali.get("type", "any"), expect)

                msg = vali.get("msg", None)
                msg = self.parse_data_in_step(msg)

                func = self.debugtalk_func_map.get(assert_key, None)  # 自定义断言方法
                if not func and hasattr(comparators, assert_key):
                    func = getattr(comparators, assert_key)

                if not func:
                    self.logger.error(f'断言方法【{assert_key}】未找到方法')
                    self.set_step_failed()
                    return self
                    # raise AttributeError(f'未找到方法：{vali["assert"]}')
                check_value = ""
                try:
                    source_way = vali.get("sourceWay", None)
                    if source_way == AssertOriginalEnum.expression.value:
                        check_value = self.__get_validate_key(check_key)
                    elif source_way == AssertOriginalEnum.original.value:
                        check_value = check_key
                    else:
                        self.logger.warning(f"当前实际值来源类型不支持： {vali}")
                        continue
                    func(check_value, expect, msg)
                    self.logger.info(f'断言成功，{assert_key}({check_key}, {expect}, {msg})')
                    self.logger.info(f'断言成功，{assert_key}({check_value}, {expect}, {msg})')

                except Exception as e:
                    error_info = self.case_runner.handler.get_log()
                    self.step_data.result.logs.after_response += error_info

                    self.set_step_failed()
                    self.logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')
                    self.logger.error(f'断言失败：{e}')

                    error_info = self.case_runner.handler.get_log()
                    self.step_data.result.logs.after_response += error_info
                    self.step_data.result.logs.error += error_info

                    if not isinstance(e, AssertionError):
                        self.logger.exception(e)

                    continue
            self.logger.info(f"{self.step_data.name} 校验完成")
        except Exception as e:

            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info

            self.set_step_failed()
            self.logger.error(f'断言失败：error:{json.dumps({"args": str(e)}, indent=4, ensure_ascii=False)}')
            logger.exception(e)

            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info
            self.step_data.result.logs.error += error_info

        return self

    def __get_validate_key(self, key):
        if key == 'status_code':
            return self.response.status_code

        if key == 'headers':
            return self.response.headers

        if key == 'cookies':
            return self.response.cookies

        if key == 'json':
            return self.response.json()

        if key == 'body':
            return self.response.body

        if key == 'text' or key == 'html':
            return self.response.text

        if key == 'content':
            return self.response.content

        if key.startswith('body.'):
            if hasattr(self.response, "body"):
                data = self.response.body
            elif hasattr(self.response, "text"):
                data = self.response.text
            else:
                data = self.response.text

            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = data

            par_data = jmespath.search(key[5:], data)
        elif key.startswith('json.'):
            par_data = jmespath.search(key[5:], self.response.json())
        elif key.startswith('re.'):
            par_data = re.search(key[3:], self.response.text)
        else:
            par_data = jmespath.search(key, self.response.json())

        # if isinstance(par_data, (dict, list, tuple)):
        #     par_data = json.dumps(par_data, ensure_ascii=False)
        return par_data


class Websocket(RequestRunner):
    """
    websocket 运行器
    """

    def __init__(self, case_runner: CaseRunner, step_data: TStepForHandle):
        super(Websocket, self).__init__(case_runner, step_data)
        self.response = None

    async def request(self):
        try:
            start_time = time.time()
            self.logger.info(f'{self.step_data.name} 开始执行')
            request_data = self.step_data.request.model_dump(by_alias=True)

            if not request_data["recv_num"]:
                request_data["recv_num"] = 3

            self.handler_forward_url(request_data)
            self.logger.info(f"websocket请求数据： {request_data}")

            res_content = []
            res_headers = {}

            if self.case_runner.run_info.forward_config.forward and self.case_runner.run_info.forward_config.agent_code:
                self.logger.info(f"通过调用客户机转发， 客户机：{self.case_runner.run_info.forward_config.agent_code}")
                request_data["requestType"] = self.step_data.step_type
                agent_res_data: HandleResponse = await send_message(self.case_runner.run_info.forward_config.agent_code,
                                                                    request_data
                                                                    )
                if agent_res_data.status_code != AgentResponseEnum.SUCCESS.value:
                    raise AgentForwardError("", f"客户机异常： {agent_res_data.message}")

                res_response: AgentResponseWebSocket = agent_res_data.response
                res_content = res_response.websocket_data
                res_headers = res_response.response_headers

            else:
                async with websockets.connect(request_data["url"]) as websocket:
                    self.logger.info(f'{self.step_data.name} 连接成功')
                    await websocket.send(request_data["data"])
                    self.logger.info(f'{self.step_data.name} 发送数据成功')

                    res_content = []
                    self.logger.info(f'{self.step_data.name} 开始接收数据')
                    for i in range(request_data["recv_num"]):
                        response = await websocket.recv()
                        res_content.append(response)

                    res_headers = dict(websocket.response_headers)

            self.logger.info(f'{self.step_data.name} 接收数据成功')
            self.logger.info(f'响应数据：{res_content}')

            response_data = ResponseData()
            response_data.text = json.dumps(res_content, ensure_ascii=False)
            response_data.content = res_content
            response_data.status_code = 200
            response_data.headers = res_headers

            self.step_data.result.response = response_data
            # self.response = Response(response_data, self.step_data.request)
            end_time = time.time()
            self.format_time(start_time, end_time)
            if self.step_data.think_time.limit:
                await asyncio.sleep(self.step_data.think_time.limit)
        except Exception as e:
            self.step_data.result.logs.after_response += self.case_runner.handler.get_log()
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
            self.set_step_failed()
            self.logger.exception(e)
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.before_request += error_info
            self.step_data.result.logs.error += error_info
            return self

        return self


class WebSocketClient:
    def __init__(self, uri):
        self.uri = uri
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_loop, args=(self.loop,))
        self.thread.start()
        self.connected_event = threading.Event()
        self.connection = None

    def start_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect())

    async def connect(self):
        self.connection = await websockets.connect(self.uri)
        self.connected_event.set()

    def send(self, message):
        asyncio.run_coroutine_threadsafe(self._send(message), self.loop)

    async def _send(self, message):
        await self.connected_event.wait()
        await self.connection.send(message)

    def receive(self):
        future = asyncio.run_coroutine_threadsafe(self._receive(), self.loop)
        return future.result()

    async def _receive(self):
        await self.connected_event.wait()
        return await self.connection.recv()

    def close(self):
        asyncio.run_coroutine_threadsafe(self._close(), self.loop).result()
        self.loop.stop()
        self.thread.join()

    async def _close(self):
        await self.connection.close()


class TestRunner(object):
    """
    单个用例执行入口，但是执行结果可能是多个用例，例如使用的参数化的情况
    """

    def __init__(self, case_data: TestCase, debugtalk_info: ProjectDebugtalkInfoModel = None,
                 run_info: CaseRunModel = None):
        asyncio.current_task().set_name(f"{case_data.case_id}_{int(datetime.now().timestamp() * 1000000)}")
        self.logger = TestLog()
        debugtalk_func_map = debugtalk_info.func_map
        if run_info.concurrent <= 1:
            for instance in debugtalk_info.module_instance:
                setattr(instance, 'logger', self.logger.logger)

        if debugtalk_func_map is None:
            debugtalk_func_map = {}

        self.run_info = run_info
        self.parameters: ParameterModel = case_data.config.parameters
        self.case_data = case_data
        self.debugtalk_func_map = debugtalk_func_map

    async def _run_for_repeat(self, case_data) -> list[TestCase]:
        all_data = []
        self.logger.logger.info(f"当前协程ID：{asyncio.current_task().get_name()}")
        for i in range(self.run_info.repeat_num):
            tem_case_data = copy.deepcopy(case_data)
            if self.run_info.repeat_num > 1:
                asyncio.current_task().set_name(f"{self.case_data.case_id}_{i}_{datetime.now().timestamp()}")
                tem_case_data.config.name = f"{tem_case_data.config.name}-{i + 1}"
                tem_case_data.case_name = f"{tem_case_data.case_name}-{i + 1}"

            runner = CaseRunner(tem_case_data, self.debugtalk_func_map, self.logger.logger, run_info=self.run_info)
            await runner.run()
            all_data.append(runner.case_data)
        return all_data

    async def start(self) -> list[TestCase]:
        try:
            return await self._run_for_repeat(self.case_data)
        except Exception as e:
            self.logger.reset()
            logger.error(f"测试用例执行失败：{e}")
            logger.exception(e)
            raise TestFailError(f"测试用例执行失败: {e}")


def formate_response_body(response: requests.Response | None) -> dict | str:
    if response is None:
        return response
    try:

        if hasattr(response, "body") and not isinstance(response.body, bytes):
            body = response.body
        else:
            body = response.json()

    except json.decoder.JSONDecodeError:
        body = response.text
    return body
