import asyncio
import copy
from datetime import datetime, timezone, timedelta
import json
import re
import threading
import time

import jmespath
import requests
import websockets

from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo_detail_for_handle import ParameterModel
from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TStep, TRequest, TWebsocket, ResponseData, \
    TestCaseSummary, StepResult, ReqRespData, SessionData, Result
from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum, ParameterTypeEnum
from module_hrm.exceptions import TestFailError
from module_hrm.utils import debugtalk_common, comparators
from module_hrm.utils.CaseRunLogHandle import RunLogCaptureHandler, TestLog
from module_hrm.utils.common import key_value_dict, update_or_extend_list, dict2list
from module_hrm.utils.parser import parse_data
from module_hrm.utils.util import replace_variables, get_func_map, ensure_str, compress_text, decompress_text
from module_hrm.dao.case_dao import CaseDao
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
import urllib3

# 忽略requests库https请求的警告
urllib3.disable_warnings()


class Response:
    def __init__(self, response_data: ResponseData, request: TRequest | TWebsocket = None):
        self.status_code = response_data.status_code
        self.headers = response_data.headers
        self.content = response_data.content
        self.cookies = response_data.cookies
        self.request: TRequest = request
        self.body = ""

    @property
    def text(self) -> str:
        if isinstance(self.content, bytes):
            return self.content.decode('utf-8')
        elif isinstance(self.content, (dict, list, tuple)):
            return json.dumps(self.content, ensure_ascii=False)
        else:
            return self.content

    def json(self) -> dict | list:

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
    def __init__(self, case_data: TestCase, debugtalk_func_map={}, logger=None):
        self.case_data = case_data
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

    def close_handler(self):
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

        for step in self.case_data.teststeps:

            if step.setup_hooks:
                try:
                    for setup_hook in step.setup_hooks:
                        hook = setup_hook.get("key", None)
                        if not hook: continue
                        var = key_value_dict(self.case_data.config.variables)
                        data = parse_data(hook, var, self.debugtalk_func_map)
                except Exception as setupre:
                    logger.error(f"setup_hook：{setupre}")
                    logger.exception(setupre)

            if step.step_type == TstepTypeEnum.http.value:
                step_obj = RequestRunner(self, step).request().validate()
            elif step.step_type == TstepTypeEnum.websocket.value:
                step_obj = Websocket(self, step)
                await step_obj.run()
                step_obj = step_obj.validate()
            else:
                raise Exception(f"step type {step.step_type} not support")

            log_content = self.handler.get_log()
            step_obj.step_data.result.logs.after_response += log_content

            step_obj.step_data.result.logs = compress_text(step_obj.step_data.result.logs.model_dump_json())
            step_obj.step_data.result.response = compress_text(step_obj.step_data.result.response.model_dump_json())

            update_or_extend_list(self.case_data.config.variables, dict2list(step_obj.extract_variable))

            if step.teardown_hooks:
                try:
                    for teardown_hook in step.teardown_hooks:
                        hook = teardown_hook.get("key", None)
                        if not hook: continue
                        var = key_value_dict(self.case_data.config.variables)
                        parse_data(hook, var, self.debugtalk_func_map)
                except Exception as setupre:
                    logger.error(f"teardown_hook：{setupre}")
                    logger.exception(setupre)

            # del step_obj.debugtalk_func_map
        end_info = f"{'执行结束用例：' + self.case_data.config.name + '<<<':<^100}"
        logger.info(end_info)
        self.logger.info(end_info)
        del self.debugtalk_func_map

        end_time = datetime.now(timezone.utc)
        self.case_data.config.result.end_time_stamp = end_time.timestamp()
        self.case_data.config.result.end_time_iso = end_time.astimezone(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S")
        self.case_data.config.result.duration = (end_time - start_time).microseconds / 1000000

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
    def __init__(self, case_runner: CaseRunner, step_data: TStep):
        self.logger = case_runner.logger
        self.case_runner = case_runner
        self.debugtalk_func_map = case_runner.debugtalk_func_map
        self.step_data = step_data
        if not self.step_data.request.url.startswith("http"):
            self.step_data.request.url = self.case_runner.case_data.config.base_url + self.step_data.request.url
        self.files = None
        self.response: Response = None
        self.extract_variable: dict = {}
        self.step_data.result = Result()

    def format_time(self, start_time: int | float, end_time: int | float):
        self.step_data.result.duration = round(end_time - start_time, 2)
        self.step_data.result.start_time_stamp = start_time
        self.step_data.result.start_time_iso = datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")
        self.step_data.result.end_time_stamp = end_time
        self.step_data.result.end_time_iso = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")

    def set_step_failed(self):
        self.step_data.result.status = CaseRunStatus.failed.value
        self.step_data.result.success = False
        self.case_runner.case_data.config.result.status = CaseRunStatus.failed.value
        self.case_runner.case_data.config.result.success = False

    def parse_request_data(self):
        temp_all_val = copy.deepcopy(self.case_runner.case_data.config.variables)
        update_or_extend_list(temp_all_val, self.step_data.variables)
        self.step_data.variables = temp_all_val

        request_data = self.step_data.request.model_dump(by_alias=True)

        temp_all_val_dict = key_value_dict(temp_all_val)
        request_data = parse_data(request_data,
                                  temp_all_val_dict,
                                  self.debugtalk_func_map)
        return request_data

    def before_teststep_handler(self, request_data: dict):
        # 请求前的回调
        before_teststep = self.debugtalk_func_map.get("before_teststep", None)
        if before_teststep:
            try:
                request_data = before_teststep(request_data)
                request_data = parse_data(request_data,
                                          key_value_dict(self.case_runner.case_data.config.variables),
                                          self.debugtalk_func_map)
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

    def after_teststep_handler(self, response: Response):
        # 响应回调
        self.logger.info(f"{self.step_data.name} 开始执行响应回调")
        try:
            after_teststep = self.debugtalk_func_map.get("after_teststep", None)
            if after_teststep:
                after_teststep(response)
            self.step_data.result.response.body = response.body
            self.step_data.result.response.text = response.text
            self.step_data.result.response.content = response.content
            self.step_data.result.response.headers = response.headers
            self.step_data.result.response.cookies = response.cookies
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

    def request(self):
        request_data = self.parse_request_data()
        # 处理json变量，如果整体都是变量直接替换后再json.loads会报错
        json_data = request_data.get("json", None)
        if json_data and isinstance(json_data, str):
            temp_all_val = copy.deepcopy(self.case_runner.case_data.config.variables)
            update_or_extend_list(temp_all_val, self.step_data.variables)
            json_data_parsed = parse_data(json_data, key_value_dict(temp_all_val), self.debugtalk_func_map)
            json_data_obj = json.loads(json_data_parsed)
            self.step_data.request.req_json = json_data_obj

        request_data_obj = TRequest(**request_data)
        re_data = request_data_obj.data
        re_json = request_data_obj.req_json
        re_param = request_data_obj.params
        re_headers = request_data_obj.headers
        re_cookies = request_data_obj.cookies
        if isinstance(re_data, str):
            request_data_obj.data = json.loads(re_data)
        if re_json and isinstance(re_json, str):
            request_data_obj.req_json = json.loads(re_json)
        if isinstance(re_param, str):
            request_data_obj.params = json.loads(re_param)
        if isinstance(re_headers, str):
            request_data_obj.headers = json.loads(re_headers)
        if isinstance(re_cookies, str):
            request_data_obj.cookies = json.loads(re_cookies)
        request_data = request_data_obj.model_dump(by_alias=True)

        request_data.pop("dataType", None)
        # request_data['json'] = request_data.pop("req_json")
        request_data.pop("upload")

        self.step_data.request = TRequest(**request_data)
        request_data["data"] = key_value_dict(self.step_data.request.data)
        request_data["params"] = key_value_dict(self.step_data.request.params)
        request_data["headers"] = key_value_dict(self.step_data.request.headers)
        request_data["cookies"] = key_value_dict(self.step_data.request.cookies)

        if self.before_teststep_handler(request_data) == CaseRunStatus.failed.value:
            return self

        logger.info(f'{">>>请求:" + self.step_data.name:=^100}')
        self.logger.info(f'{">>>请求:" + self.step_data.name:=^100}')
        logger.info(f"url: {self.step_data.request.url}")
        self.logger.info(f"url: {self.step_data.request.url}")
        logger.info(f"method: {self.step_data.request.method}")
        self.logger.info(f"method: {self.step_data.request.method}")
        logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")
        self.logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")

        try:
            self.step_data.result.logs.before_request += self.case_runner.handler.get_log()
            start_time = time.time()
            res_response = requests.request(**request_data)
            end_time = time.time()
            self.format_time(start_time, end_time)

            if self.step_data.think_time.limit:
                time.sleep(self.step_data.think_time.limit)

            res_obj = ResponseData()
            res_obj.text = res_response.text
            res_obj.content = res_response.content.decode("utf8")
            res_obj.status_code = res_response.status_code
            res_obj.headers = dict(res_response.headers)
            res_obj.cookies = dict(res_response.cookies)
            self.step_data.result.response = res_obj
            self.response = Response(res_obj, self.step_data.request)
        except Exception as e:
            logger.exception(e)
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
            self.response = None
            self.set_step_failed()
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.before_request += error_info
            self.step_data.result.logs.error += error_info
            return self

        if self.after_teststep_handler(self.response) == CaseRunStatus.failed.value:
            return self
        self.step_data.result.response.body = self.response.body

        self.extract_data()

        logger.info(f'request.headers: {json.dumps(self.response.request.headers, indent=4, ensure_ascii=False)}')
        self.logger.info(
            f'request.headers: {json.dumps(self.response.request.headers, indent=4, ensure_ascii=False)}')
        # logger.info(f'request.body: {self.response.request.body}')
        # self.logger.info(f'request.body: {ensure_str(self.response.request.body)}')

        logger.info(f'{"<<<请求结果:" + self.step_data.name:=^100}')
        self.logger.info(f'{"<<<请求结果:" + self.step_data.name:=^100}')
        logger.info(f'status_code: {self.response.status_code}')
        self.logger.info(f'status_code: {self.response.status_code}')
        logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        self.logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        logger.info(f'response.text: {self.response.text}')
        self.logger.info(
            f'response.text: {self.response.text}')
        logger.info(f'{"请求:" + self.step_data.name + "<<<":=^100}')
        self.logger.info(f'{"请求:" + self.step_data.name + "<<<":=^100}')

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
            return self
        except Exception as e:
            self.set_step_failed()
            logger.error("提取变量失败")
            logger.error(e)
            self.logger.error(f'{self.step_data.name} 提取变量失败\n {e}')
            self.logger.exception(e)
            error_info = self.case_runner.handler.get_log()
            self.step_data.result.logs.after_response += error_info
            self.step_data.result.logs.error += error_info

    def validate(self):
        # 校验数据处理回调
        self.logger.info(f"{self.step_data.name} 开始校验")
        before_request_validate = self.debugtalk_func_map.get("before_request_validate", None)
        if before_request_validate:
            before_request_validate(self.step_data.validators)

        temp_var = copy.deepcopy(self.case_runner.case_data.config.variables)
        update_or_extend_list(temp_var, dict2list(self.extract_variable))
        temp_var = key_value_dict(temp_var)
        for vali in self.step_data.validators:
            assert_key = vali["assert"]
            assert_key = parse_data(assert_key, temp_var, self.debugtalk_func_map)
            check_key = vali["check"]
            check_key: str = parse_data(check_key, temp_var, self.debugtalk_func_map)
            expect = vali["expect"]
            expect = parse_data(expect, temp_var, self.debugtalk_func_map)

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

            try:
                func(self.__get_validate_key(check_key), expect, msg)
                self.logger.info(f'断言成功，{assert_key}({check_key}, {expect}, {msg})')
            except Exception as e:
                logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')
                logger.exception(e)
                self.set_step_failed()
                # self.logger.error(f'{e}')
                self.logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')

                self.logger.exception(e)
                error_info = self.case_runner.handler.get_log()
                self.step_data.result.logs.after_response += error_info
                self.step_data.result.logs.error += error_info
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

    def __init__(self, case_runner: CaseRunner, step_data: TStep):
        super(Websocket, self).__init__(case_runner, step_data)
        self.response = None

    async def run(self):
        self.logger.info(f'{self.step_data.name} 开始执行')
        request_data = self.parse_request_data()
        self.step_data.request = TWebsocket(**request_data)
        if self.before_teststep_handler(self.step_data.request.model_dump(by_alias=True)) == CaseRunStatus.failed.value:
            return self

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
                self.response = Response(response_data, self.step_data.request)
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

        if self.after_teststep_handler(self.response) == CaseRunStatus.failed.value:
            return self

        self.extract_data()

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


class ParametersHandler(object):
    """
    参数处理器，用于处理参数化的情况
    """
    def __init__(self, parameters):
        self.parameters: ParameterModel = parameters

    def get_parameters(self):
        parameters = []
        if self.parameters.type == ParameterTypeEnum.local_table.value:
            parameter_source = decompress_text(self.parameters.value)
            parameter_obj = json.loads(parameter_source)
            headers = parameter_obj.get("tableHeaders", [])
            datas = parameter_obj.get("tableDatas", [])

            for data in datas:
                # 只使用可用的数据
                if not data.get("__enable", True):
                    continue
                param = []
                for item in data:
                    # 排除状态字段
                    if item == "__enable":
                        continue
                    param.append({
                        "key":item,
                        "value": data[item]["content"],
                        "enable": True,
                        "type": "string"
                    })
                    # param[item] = data[item]["content"]
                parameters.append(param)
        return parameters


class TestRunner(object):
    """
    单个用例执行入口，但是执行结果可能是多个用例，例如使用的参数化的情况
    """

    def __init__(self, case_data: TestCase, debugtalk_func_map={}):
        self.parameters: ParameterModel = case_data.config.parameters
        self.case_data = case_data
        self.debugtalk_func_map = debugtalk_func_map
        self.logger = TestLog()

    async def start(self) -> list[CaseRunner]:
        try:
            # 处理before_test, 执行开始测试之前的回调
            before_test = self.debugtalk_func_map.get("before_test", None)
            if before_test:
                try:
                    logger.info("开始处理before_test")
                    before_test(self.case_data.config.variables)
                    logger.info("before_test处理完成")
                except Exception as e:
                    logger.error(f"before_test处理失败：{e}")
                    logger.exception(e)
                    raise TestFailError(f"before_test处理失败")

            if self.case_data.config.setup_hooks:
                try:
                    for setup_hook in self.case_data.config.setup_hooks:
                        hook = setup_hook.get("key", None)
                        if not hook: continue
                        var = key_value_dict(self.case_data.config.variables)
                        parse_data(hook, var, self.debugtalk_func_map)
                except Exception as setupre:
                    logger.error(f"setup_hooks处理失败：{setupre}")
                    logger.exception(setupre)

            if not self.parameters.value:
                runner = CaseRunner(self.case_data, self.debugtalk_func_map, self.logger.logger)
                await runner.run()
                data = runner.close_handler()
                return [data]

            params = ParametersHandler(self.parameters).get_parameters()

            all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
            for param in params:
                tmp_case_data = copy.deepcopy(self.case_data)
                old_variables: list[dict] = tmp_case_data.config.variables
                update_or_extend_list(old_variables, param)
                # old_variables.update(param)
                tmp_case_data.config.variables = old_variables
                name = tmp_case_data.config.name
                if "case_name" in param:
                    tmp_case_data.config.name = f"{name}[{param['case_name']}]"
                runner = CaseRunner(tmp_case_data, self.debugtalk_func_map, self.logger.logger)
                await runner.run()
                data = runner.close_handler()
                all_data.append(data)
            return all_data
        except Exception as e:
            self.logger.reset()
            logger.error(f"测试用例执行失败：{e}")
            logger.exception(e)
            raise TestFailError(f"测试用例执行失败: {e}")
        finally:
            if self.case_data.config.teardown_hooks:
                try:
                    for teardown_hook in self.case_data.config.teardown_hooks:
                        hook = teardown_hook.get("key", None)
                        if not hook: continue
                        var = key_value_dict(self.case_data.config.variables)
                        parse_data(hook, var, self.debugtalk_func_map)
                except Exception as setupre:
                    logger.error(f"teardown_hook处理失败：{setupre}")
                    logger.exception(setupre)


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
