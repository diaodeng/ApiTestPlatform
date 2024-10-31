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

from module_hrm.entity.vo.case_vo import CaseRunModel
from module_hrm.entity.vo.case_vo_detail_for_handle import ParameterModel, TStep as TStepForHandle
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TStep as TStepForRun, TRequest as TRequestForRun, \
    TWebsocket, ResponseData, \
    Result
from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum
from module_hrm.exceptions import TestFailError
from module_hrm.utils import comparators
from module_hrm.utils.CaseRunLogHandle import RunLogCaptureHandler, TestLog, CustomStackLevelLogger
from module_hrm.utils.common import key_value_dict, update_or_extend_list, dict2list
from module_hrm.utils.parser import parse_data, parse_function_set_default_params
from module_hrm.utils.util import replace_variables, compress_text
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
        self.body = ""  # 默认不会有值，用于在回调中设置自己转换后的内容

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


class CaseRunner(object):
    def __init__(self, case_data: TestCase, debugtalk_func_map={}, logger: CustomStackLevelLogger = None,
                 run_info: CaseRunModel = None):
        self.case_data = case_data
        self.run_info = run_info
        self.logger = logger
        self.handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)

        # default_func_map: dict = copy.deepcopy(get_func_map(debugtalk_common))  # 公用debugtalk方法
        # default_func_map.update(debugtalk_func_map)
        self.debugtalk_func_map: dict = debugtalk_func_map  # 对应项目debugtalk方法
        # 全局变量中自身替换
        self.case_data.config.variables = json.loads(
            parse_data(json.dumps(self.case_data.config.variables), key_value_dict(self.case_data.config.variables),
                       self.debugtalk_func_map))

    def __before_case(self):
        # 处理before_test, 执行开始测试之前的回调
        before_test = self.debugtalk_func_map.get("before_case_test", None)
        if before_test:
            try:
                logger.info("开始处理before_test")
                self.logger.info("开始处理before_test")
                before_test(self.case_data)
                logger.info(f"before_case_test处理完成:{self.case_data.model_dump_json(by_alias=True)}")
                self.logger.info(f"before_case_test处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            except Exception as e:
                logger.error(f"before_test处理失败：{e}")
                logger.exception(e)
                self.logger.error(f"before_test处理失败：{e}")
                self.logger.exception(e)
                self.case_data.config.result.status = CaseRunStatus.failed.value
                raise TestFailError(f"before_test处理失败")

    def __case_setup(self):
        if self.case_data.config.setup_hooks:
            try:
                for setup_hook in self.case_data.config.setup_hooks:
                    hook = setup_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_data.config.variables)
                    parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.case_data,))
                    logger.info(f"case_setup处理完成:{self.case_data.model_dump_json(by_alias=True)}")
                    self.logger.info(f"case_setup处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            except Exception as setupre:
                logger.error(f"case setup_hooks error：{setupre}")
                logger.exception(setupre)
                self.logger.error(f"case setup_hooks error：{setupre}")
                self.logger.exception(setupre)
                self.case_data.config.result.status = CaseRunStatus.failed.value

    def __after_case(self):
        before_test = self.debugtalk_func_map.get("after_case_test", None)
        if before_test:
            try:
                logger.info("开始处理after_test")
                self.logger.info("开始处理after_test")
                before_test(self.case_data)
                logger.info(f"after_case_test处理完成:{self.case_data.model_dump_json(by_alias=True)}")
                self.logger.info(f"after_case_test处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            except Exception as e:
                logger.error(f"after_test error：{e}")
                self.logger.error(f"after_test error：{e}")
                logger.exception(e)
                self.logger.exception(e)
                self.case_data.config.result.status = CaseRunStatus.failed.value
                raise TestFailError(f"after_test处理失败")

    def __case_teardown(self):
        if self.case_data.config.teardown_hooks:
            try:
                for teardown_hook in self.case_data.config.teardown_hooks:
                    hook = teardown_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_data.config.variables)
                    parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.case_data,))
                    logger.info(f"case_teardown处理完成:{self.case_data.model_dump_json(by_alias=True)}")
                    self.logger.info(f"case_teardown处理完成:{self.case_data.model_dump_json(by_alias=True)}")
            except Exception as setupre:
                logger.error(f"case teardown_hook error：{setupre}")
                self.logger.error(f"case teardown_hook error：{setupre}")
                logger.exception(setupre)
                self.logger.exception(setupre)
                self.case_data.config.result.status = CaseRunStatus.failed.value

    def __close_handler(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
        del self.handler
        return self

    async def run(self):
        start_info = f"{'>>>开始执行用例：' + self.case_data.config.name:>^100}"
        # self.case_data.config.result = Result()
        setattr(self.case_data.config, "result", Result())
        logger.info(start_info)
        self.logger.info(start_info)
        start_time = datetime.now(timezone.utc)
        self.case_data.config.result.start_time_stamp = start_time.timestamp()
        self.case_data.config.result.start_time_iso = start_time.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S")

        self.__before_case()
        self.__case_setup()

        last_step_obj = None
        for index, step in enumerate(self.case_data.teststeps):

            if step.step_type == TstepTypeEnum.http.value:
                step_obj = RequestRunner(self, step)
                await step_obj.run()
                step_obj = step_obj.validate()
            elif step.step_type == TstepTypeEnum.websocket.value:
                step_obj = Websocket(self, step)
                await step_obj.run()
                step_obj = step_obj.validate()
            else:
                raise Exception(f"step type {step.step_type} not support")

            last_step_obj = step_obj

            if index < len(self.case_data.teststeps) - 1:
                log_content = self.handler.get_log()
                step_obj.step_data.result.logs.after_response += log_content

                step_obj.step_data.result.logs = compress_text(step_obj.step_data.result.logs.model_dump_json())
                step_obj.step_data.result.response = compress_text(step_obj.step_data.result.response.model_dump_json())

            update_or_extend_list(self.case_data.config.variables, dict2list(step_obj.extract_variable))

            self.case_data.teststeps[index] = step_obj.step_data

            # del step_obj.debugtalk_func_map
        end_info = f"{'执行结束用例：' + self.case_data.config.name + '<<<':<^100}"
        logger.info(end_info)
        self.logger.info(end_info)

        end_time = datetime.now(timezone.utc)
        logger.debug(f"用例{self.case_data.config.name}执行完成，耗时：{end_time - start_time}")
        logger.debug(f"用例{self.case_data.config.name}执行完成，耗时calc：{(end_time - start_time).total_seconds()}")
        self.case_data.config.result.end_time_stamp = end_time.timestamp()
        self.case_data.config.result.end_time_iso = end_time.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S")
        logger.debug(f"用例{self.case_data.config.name}执行完成时间，format：{self.case_data.config.result.end_time_iso}")
        self.case_data.config.result.duration = (end_time - start_time).total_seconds()

        self.__after_case()
        self.__case_teardown()

        log_content = self.handler.get_log()
        last_step_obj.step_data.result.logs.after_response += log_content

        last_step_obj.step_data.result.logs = compress_text(last_step_obj.step_data.result.logs.model_dump_json())
        last_step_obj.step_data.result.response = compress_text(
            last_step_obj.step_data.result.response.model_dump_json())

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
        logger.debug(f"用例{self.case_runner.case_data.config.name}执行完成时间，step耗时：{end_time - start_time}")
        logger.debug(
            f"用例{self.case_runner.case_data.config.name}执行完成时间，step format：{datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")

    def set_step_failed(self):
        self.step_data.result.status = CaseRunStatus.failed.value
        self.step_data.result.success = False
        self.case_runner.case_data.config.result.status = CaseRunStatus.failed.value
        self.case_runner.case_data.config.result.success = False

    def parse_request_data(self):
        temp_all_val = copy.deepcopy(self.case_runner.case_data.config.variables)
        update_or_extend_list(temp_all_val, self.step_data.variables)
        self.step_data.variables = temp_all_val

        step_data = self.step_data.model_dump(by_alias=True)
        request_data = step_data["request"]

        temp_all_val_dict = key_value_dict(temp_all_val)
        request_data = parse_data(request_data,
                                  temp_all_val_dict,
                                  self.debugtalk_func_map)

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

    def before_teststep_handler(self):
        # 请求前的回调
        before_teststep: Callable = self.debugtalk_func_map.get("before_test_step", None)
        if before_teststep:
            try:
                request_data = before_teststep(self.step_data)
                request_data = parse_data(request_data,
                                          key_value_dict(self.case_runner.case_data.config.variables),
                                          self.debugtalk_func_map)
                logger.info(f"系统before_teststep回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
                self.logger.info(f"系统before_teststep回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
                return request_data
            except Exception as e:
                logger.exception(e)
                self.step_data.result.logs.before_request += self.case_runner.handler.get_log()
                self.set_step_failed()
                self.logger.error(f"before_teststep函数执行失败: {e}")
                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.before_request += error_info
                self.step_data.result.logs.error += error_info
                return CaseRunStatus.failed.value

    def after_teststep_handler(self):
        # 响应回调
        self.logger.info(f"{self.step_data.name} 开始执行响应回调")
        try:
            after_teststep: Callable = self.debugtalk_func_map.get("after_test_step", None)
            if after_teststep:
                after_teststep(self.step_data)
            logger.info(f"系统after_teststep回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            self.logger.info(f"系统after_teststep回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            self.logger.info(f"{self.step_data.name} 响应回调执行完毕")
        except Exception as ef:
            self.step_data.result.logs.after_response += self.case_runner.handler.get_log()
            self.set_step_failed()
            logger.exception(ef)
            self.logger.info(f"response.text: {self.response.text}")
            self.logger.error(
                f'回调after_teststep处理异常，error:{json.dumps({"args": str(ef.args), "msg": str(ef)}, indent=4, ensure_ascii=False)}')
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info
            self.step_data.result.logs.error += error_info
            return CaseRunStatus.failed.value

    def teststep_setup_handler(self):
        if self.step_data.setup_hooks:
            try:
                for setup_hook in self.step_data.setup_hooks:
                    hook = setup_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_runner.case_data.config.variables)
                    data = parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.step_data,))
                    logger.info(f"自定义teststep_setup回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
                    self.logger.info(
                        f"自定义teststep_setup回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            except Exception as setupre:
                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.before_request += error_info

                self.set_step_failed()

                self.logger.error(f"setup_hook error：{setupre}")
                self.logger.exception(setupre)

                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.before_request += error_info
                self.step_data.result.logs.error += error_info
                return CaseRunStatus.failed.value

    def teststep_tearndown_handler(self):
        if self.step_data.teardown_hooks:
            try:
                for teardown_hook in self.step_data.teardown_hooks:
                    hook = teardown_hook.get("key", None)
                    if not hook: continue
                    var = key_value_dict(self.case_runner.case_data.config.variables)
                    parse_function_set_default_params(hook, var, self.debugtalk_func_map, (self.step_data,))
                    logger.info(
                        f"自定义teststep_tearndown回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
                    self.logger.info(
                        f"自定义teststep_tearndown回调之后的数据：{self.step_data.model_dump_json(by_alias=True)}")
            except Exception as setupre:
                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.after_response += error_info

                self.set_step_failed()

                self.logger.error(f"teardown_hook error：{setupre}")
                self.logger.exception(setupre)

                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.after_response += error_info
                self.step_data.result.logs.error += error_info
                return CaseRunStatus.failed.value

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

    async def run(self):
        """
        执行统一调用这个方法
        """
        self.parse_request_data()

        # 系统回调
        if self.before_teststep_handler() == CaseRunStatus.failed.value:
            return self

        # 自定义回调
        if self.teststep_setup_handler() == CaseRunStatus.failed.value:
            return self

        logger.info(f'{">>>请求:" + self.step_data.name:=^100}')
        self.logger.info(f'{">>>请求:" + self.step_data.name:=^100}')
        logger.info(f"url: {self.step_data.request.url}")
        self.logger.info(f"url: {self.step_data.request.url}")

        await self.request()

        if self.after_teststep_handler() == CaseRunStatus.failed.value:
            return self

        if self.teststep_tearndown_handler() == CaseRunStatus.failed.value:
            return self

        self.response = Response(self.step_data.result.response, self.step_data.request)

        self.step_data.result.response.body = self.response.body

        self.extract_data()

        self.step_data = TStepForHandle(**self.step_data.model_dump(by_alias=True))  ## 数据转回原来的格式

        return self

    async def request(self):
        """
        不同的请求类型自行重写这个方法
        """

        request_data = self.step_data.request.model_dump(by_alias=True)

        logger.info(f"method: {self.step_data.request.method}")
        self.logger.info(f"method: {self.step_data.request.method}")
        logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")
        self.logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")

        try:
            self.step_data.result.logs.before_request += self.case_runner.handler.get_log()
            request_data.pop("dataType", None)
            request_data.pop("upload")
            request_data["follow_redirects"] = request_data.pop("allow_redirects", True)
            request_data.pop("verify", True)

            start_time = time.time()
            start_request_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            logger.debug(
                f"发起请求，请求时间:{start_request_time} >> {self.case_runner.case_data.config.name}")
            async with httpx.AsyncClient() as client:
                res_response = await client.request(**request_data)
            logger.debug(
                f"请求完成，完成时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')} >> {self.case_runner.case_data.config.name}")
            end_time = time.time()
            self.format_time(start_time, end_time)

            if self.step_data.think_time.limit:
                await asyncio.sleep(self.step_data.think_time.limit)

            logger.info(f'{"<<<请求结束:" + self.step_data.name:=^100}')
            self.logger.info(f'{"<<<请求结束:" + self.step_data.name:=^100}')
            logger.info(f'status_code: {res_response.status_code}')
            self.logger.info(f'status_code: {res_response.status_code}')
            logger.info(f'response.headers: {json.dumps(dict(res_response.headers), indent=4, ensure_ascii=False)}')
            self.logger.info(
                f'response.headers: {json.dumps(dict(res_response.headers), indent=4, ensure_ascii=False)}')
            logger.info(f'response.text: {res_response.text}')
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
            if not (isinstance(e, requests.exceptions.RequestException) \
                    or isinstance(e, requests.exceptions.ReadTimeout)):
                logger.exception(e)
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
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
                val = self.__get_validate_key(item["value"])
                self.extract_variable[item["key"]] = val
            logger.info(f'{self.step_data.name} extract_variable: {self.extract_variable}')
            self.logger.info(f'{self.step_data.name} extract_variable: {json.dumps(self.extract_variable)}')
            self.logger.info(f"{self.step_data.name} 变量提取完成")
            update_or_extend_list(self.case_runner.case_data.config.variables, dict2list(self.extract_variable))
            return self
        except Exception as e:
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info

            self.set_step_failed()
            logger.error("提取变量失败")
            logger.error(e)
            self.logger.error(f'{self.step_data.name} 提取变量失败\n {e}')
            self.logger.exception(e)

            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info
            self.step_data.result.logs.error += error_info

    def validate(self):
        if not self.step_data.result.success: return self
        # 校验数据处理回调
        self.logger.info(f"{self.step_data.name} 开始校验")
        before_request_validate = self.debugtalk_func_map.get("before_request_validate", None)
        if before_request_validate:
            before_request_validate(self.step_data.validators)

        # temp_var = copy.deepcopy(self.case_runner.case_data.config.variables)
        # update_or_extend_list(temp_var, dict2list(self.extract_variable))
        temp_var = key_value_dict(self.case_runner.case_data.config.variables)
        for vali in self.step_data.validators:
            assert_key = vali["assert"]
            assert_key = parse_data(assert_key, temp_var, self.debugtalk_func_map)
            check_key = vali["check"]
            check_key: str = parse_data(check_key, temp_var, self.debugtalk_func_map)
            vali["check"] = check_key

            expect = vali["expect"]
            expect = parse_data(expect, temp_var, self.debugtalk_func_map)
            vali["expect"] = expect

            assert_expression = f'{assert_key}({check_key}, {expect})'
            msg = vali.get("msg", None)
            msg = parse_data(msg, temp_var, self.debugtalk_func_map)

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

                check_value = self.__get_validate_key(check_key)
                func(check_value, expect, msg)
                self.logger.info(f'断言成功，{assert_key}({check_key}, {expect}, {msg})')

            except Exception as e:
                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.after_response += error_info

                logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')
                logger.error(f'断言失败：{assert_key}({check_value}, {expect}, {msg})')

                self.set_step_failed()
                self.logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')
                self.logger.error(f'断言失败：{assert_key}({check_value}, {expect}, {msg})')

                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.after_response += error_info
                self.step_data.result.logs.error += error_info

                if not isinstance(e, AssertionError):
                    logger.exception(e)
                    self.logger.exception(e)

                continue
            self.logger.info("\n")
        self.logger.info(f"{self.step_data.name} 校验完成")
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
            par_data = jmespath.search(key[5:], json.loads(data))
        elif key.startswith('json.'):
            par_data = jmespath.search(key[5:], self.response.json())
        elif key.startswith('re.'):
            par_data = re.search(key[3:], self.response.text)
        else:
            par_data = jmespath.search(key, self.response.json())

        if not isinstance(par_data, str):
            par_data = json.dumps(par_data, ensure_ascii=False)
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
            async with websockets.connect(self.step_data.request.url) as websocket:
                self.logger.info(f'{self.step_data.name} 连接成功')
                await websocket.send(self.step_data.request.data)
                self.logger.info(f'{self.step_data.name} 发送数据成功')

                res_data = []
                self.logger.info(f'{self.step_data.name} 开始接收数据')
                for i in range(self.step_data.request.recv_num or 3):
                    response = await websocket.recv()
                    res_data.append(response)
                self.logger.info(f'{self.step_data.name} 接收数据成功')
                self.logger.info(f'响应数据：{res_data}')

                response_data = ResponseData()
                response_data.text = json.dumps(res_data, ensure_ascii=False)
                response_data.content = res_data
                response_data.status_code = 200
                response_data.headers = dict(websocket.response_headers)

                self.step_data.result.response = response_data
                # self.response = Response(response_data, self.step_data.request)
            end_time = time.time()
            self.format_time(start_time, end_time)
            if self.step_data.think_time.limit:
                await asyncio.sleep(self.step_data.think_time.limit)
        except Exception as e:
            self.step_data.result.logs.after_response += self.case_runner.handler.get_log()
            logger.exception(e)
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

    def __init__(self, case_data: TestCase, debugtalk_func_map: dict = None,
                 run_info: CaseRunModel = None):
        if debugtalk_func_map is None:
            debugtalk_func_map = {}

        self.run_info = run_info
        self.parameters: ParameterModel = case_data.config.parameters
        self.case_data = case_data
        self.debugtalk_func_map = debugtalk_func_map
        self.logger = TestLog()

    async def _run_for_repeat(self, case_data) -> list[TestCase]:
        all_data = []
        # if not case_data.status == CaseStatusEnum.normal.value:
        #     status = CaseRunStatus.xfailed.value
        #     if case_data.status == CaseStatusEnum.xfailed.value:
        #         status = CaseRunStatus.xfailed.value
        #     elif case_data.status == CaseStatusEnum.xpassed.value:
        #         status = CaseRunStatus.xpassed.value
        #     elif case_data.status == CaseStatusEnum.skipped.value:
        #         status = CaseRunStatus.skipped.value
        #
        #     case_data.config.result.status = status
        #     case_data.config.result.success = True
        #     for step in case_data.teststeps:
        #         step.result.success = True
        #         step.result.status = status
        #
        #     all_data.append(case_data)
        #     return all_data
        logger.info(f"当前协程ID：{asyncio.current_task().get_name()}")
        for i in range(self.run_info.repeat_num):
            tem_case_data = copy.deepcopy(case_data)
            if self.run_info.repeat_num > 1:
                tem_case_data.config.name = f"{tem_case_data.config.name}-{i + 1}"
                tem_case_data.case_name = f"{tem_case_data.case_name}-{i + 1}"
            runner = CaseRunner(tem_case_data, self.debugtalk_func_map, self.logger.logger, run_info=self.run_info)
            await runner.run()
            all_data.append(runner.case_data)
        return all_data

    async def start(self) -> list[TestCase]:
        try:
            return await self._run_for_repeat(self.case_data)
            # if not self.parameters or not self.parameters.value:
            #     return await self._run_for_repeat(self.case_data, repeat_num)
            #
            #
            # params = ParametersHandler(self.parameters).get_parameters()
            #
            # all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
            # for index, param in enumerate(params):
            #     tmp_case_data = copy.deepcopy(self.case_data)
            #     old_variables: list[dict] = tmp_case_data.config.variables
            #     update_or_extend_list(old_variables, param)
            #     tmp_param = key_value_dict(param)
            #     # old_variables.update(param)
            #     tmp_case_data.config.variables = old_variables
            #     name = tmp_case_data.config.name
            #     if "case_name" in tmp_param:
            #         tmp_case_data.config.name = f"{name}[{tmp_param['case_name']}]"
            #         tmp_case_data.case_name = f"{name}[{tmp_param['case_name']}]"
            #     else:
            #         tmp_case_data.config.name = f"{name}[{index + 1}]"
            #         tmp_case_data.case_name = f"{name}[{index + 1}]"
            #
            #     runners = await self._run_for_repeat(tmp_case_data, repeat_num)
            #     all_data.extend(runners)
            # return all_data
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
