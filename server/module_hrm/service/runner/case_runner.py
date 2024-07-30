import asyncio
import copy
import datetime
import json
import re
import threading
import time

import jmespath
import requests
import websockets

from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TStep, TRequest, TWebsocket, ResponseData, \
    TestCaseSummary, StepResult, ReqRespData, SessionData
from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum
from module_hrm.exceptions import TestFailError
from module_hrm.utils import debugtalk_common, comparators
from module_hrm.utils.CaseRunLogHandle import RunLogCaptureHandler, TestLog
from module_hrm.utils.parser import parse_data
from module_hrm.utils.util import replace_variables, get_func_map, ensure_str
from utils.log_util import logger


class Response:
    def __init__(self, response_data: ResponseData):
        self.status_code = response_data.status_code
        self.headers = response_data.headers
        self.content = response_data.content
        self.cookies = response_data.cookies

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

    @property
    def body(self) -> dict | str:
        try:
            return self.json()
        except:
            return self.text


class CaseRunner(object):
    def __init__(self, case_data: TestCase, debugtalk_func_map={}, logger=None):
        self.case_data = case_data
        self.logger = logger
        self.handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)

        self.result: TestCaseSummary = TestCaseSummary(**{"name": self.case_data.config.name})
        self.result.in_out.config_vars = self.case_data.config.variables

        default_func_map: dict = copy.deepcopy(get_func_map(debugtalk_common))  # 公用debugtalk方法
        default_func_map.update(debugtalk_func_map)
        self.debugtalk_func_map: dict = default_func_map  # 对应项目debugtalk方法
        # 全局变量中自身替换
        self.case_data.config.variables = json.loads(
            parse_data(json.dumps(self.case_data.config.variables), self.case_data.config.variables,
                       self.debugtalk_func_map))

    def close_handler(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
        del self.handler
        return self

    async def run(self):
        start_info = f"{'>>>开始执行用例：' + self.case_data.config.name:>^100}"
        logger.info(start_info)
        self.logger.info(start_info)
        start_time = datetime.datetime.utcnow()
        self.result.time.start_time = start_time.timestamp()
        self.result.time.start_time_iso_format = start_time.strftime("%Y-%m-%d %H:%M:%S")

        for step in self.case_data.teststeps:

            step.variables = parse_data(step.variables,
                                        self.case_data.config.variables,
                                        self.debugtalk_func_map
                                        )

            # 发起请求
            if step.step_type == TstepTypeEnum.api.value:
                step_obj = RequestRunner(self, step).request().validate()
            elif step.step_type == TstepTypeEnum.websocket.value:
                step_obj = Websocket(self, step)
                await step_obj.run()
                step_obj = step_obj.validate()
            log_content = self.handler.get_log()
            step_obj.result.log = log_content

            self.case_data.config.variables.update(step_obj.extract_variable)
            self.result.step_results.append(step_obj.result)
            self.result.log[step_obj.step_data.step_id] = log_content

            del step_obj.debugtalk_func_map
        end_info = f"{'执行结束用例：' + self.case_data.config.name + '<<<':<^100}"
        logger.info(end_info)
        self.logger.info(end_info)
        del self.debugtalk_func_map

        end_time = datetime.datetime.utcnow()
        self.result.time.end_time = end_time.timestamp()
        self.result.time.end_time_iso_format = end_time.strftime("%Y-%m-%d %H:%M:%S")
        self.result.time.duration = (end_time - start_time).seconds

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
        self.result: StepResult = StepResult()

        self.result.name = self.step_data.name
        self.result.step_id = self.step_data.step_id
        self.result.step_type = self.step_data.step_type

    def set_step_failed(self):
        self.result.status = CaseRunStatus.failed.value
        self.result.success = False
        self.case_runner.result.status = CaseRunStatus.failed.value
        self.case_runner.result.success = False

    def parse_request_data(self):
        temp_all_val = copy.deepcopy(self.case_runner.case_data.config.variables)
        temp_all_val.update(self.step_data.variables)

        request_data = self.step_data.request.model_dump(by_alias=True)

        request_data = parse_data(request_data,
                                  temp_all_val,
                                  self.debugtalk_func_map)
        return request_data

    def before_request(self, request_data: dict):
        # 请求前的回调
        before_request = self.debugtalk_func_map.get("before_request", None)
        if before_request:
            try:
                request_data = before_request(request_data)
                request_data = parse_data(request_data,
                                          self.case_runner.case_data.config.variables,
                                          self.debugtalk_func_map)
                return request_data
            except Exception as e:
                self.set_step_failed()
                self.logger.error(f"before_request函数执行失败: {e}")
                return CaseRunStatus.failed.value

    def after_request(self, response: requests.Response):
        # 响应回调
        self.logger.info(f"{self.step_data.name} 开始执行响应回调")
        try:
            after_request = self.debugtalk_func_map.get("after_request", None)
            if after_request:
                after_request(response)
            self.logger.info(f"{self.step_data.name} 响应回调执行完毕")
        except Exception as ef:
            self.set_step_failed()
            logger.exception(ef)
            self.logger.info(f"response.text: {self.response.text}")
            self.logger.error(
                f'回调after_request处理异常，error:{json.dumps({"args": str(ef.args), "msg": str(ef)}, indent=4, ensure_ascii=False)}')
            return CaseRunStatus.failed.value

    def request(self):
        request_data = self.parse_request_data()
        # 处理json变量，如果整体都是变量直接替换后再json.loads会报错
        json_data = request_data.get("json", None)
        if json_data and isinstance(json_data, str):
            temp_all_val = copy.deepcopy(self.case_runner.case_data.config.variables)
            temp_all_val.update(self.step_data.variables)
            json_data_parsed = parse_data(json_data, temp_all_val, self.debugtalk_func_map)
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
        if isinstance(re_json, str):
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

        if self.before_request(request_data) == CaseRunStatus.failed.value:
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
            data = SessionData()
            self.result.data = data

            req_resps_data = ReqRespData()
            req_resps_data.request = TRequest(**request_data)
            self.result.data.req_resps.append(req_resps_data)

            start_time = time.time()
            res_response = requests.request(**request_data)
            end_time = time.time()
            self.result.duration = round(end_time - start_time, 2)
            if self.step_data.think_time.limit:
                time.sleep(self.step_data.think_time.limit)

            res_obj = ResponseData()
            res_obj.content = res_response.text
            res_obj.body = res_response.content
            res_obj.status_code = res_response.status_code
            res_obj.headers = dict(res_response.headers)
            res_obj.cookies = dict(res_response.cookies)
            req_resps_data.response = res_obj
            self.response = Response(res_obj)
        except Exception as e:
            logger.exception(e)
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
            self.response = None
            self.set_step_failed()
            return self

        if self.after_request(self.response) == CaseRunStatus.failed.value:
            return self

        self.extract_data()

        logger.info(f'request.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        self.logger.info(
            f'request.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        logger.info(f'request.body: {self.response.body}')
        self.logger.info(f'request.body: {ensure_str(self.response.body)}')

        logger.info(f'{"<<<请求结果:" + self.step_data.name:=^100}')
        self.logger.info(f'{"<<<请求结果:" + self.step_data.name:=^100}')
        logger.info(f'status_code: {self.response.status_code}')
        self.logger.info(f'status_code: {self.response.status_code}')
        logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        self.logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        logger.info(f'response.text: {self.response.text}')
        self.logger.info(
            f'response.body: {self.response.body if hasattr(self.response, "body") else self.response.text}')
        logger.info(f'{"请求:" + self.step_data.name + "<<<":=^100}')
        self.logger.info(f'{"请求:" + self.step_data.name + "<<<":=^100}')

        return self

    def extract_data(self):
        """
        从请求响应中提取变量
        """
        self.logger.info(f"{self.step_data.name} 开始提取变量")
        try:
            for key in self.step_data.extract:
                val = self.__get_validate_key(self.step_data.extract[key])
                self.extract_variable[key] = val
            logger.info(f'{self.step_data.name} extract_variable: {self.extract_variable}')
            self.logger.info(f'{self.step_data.name} extract_variable: {json.dumps(self.extract_variable)}')
            self.logger.info(f"{self.step_data.name} 变量提取完成")
            return self
        except Exception as e:
            self.set_step_failed()
            logger.error("提取变量失败")
            logger.error(e)
            self.logger.error(f'{self.step_data.name} 提取变量失败\n {e}')
            self.result.status = CaseRunStatus.failed.value

    def validate(self):
        # 校验数据处理回调
        self.logger.info(f"{self.step_data.name} 开始校验")
        before_request_validate = self.debugtalk_func_map.get("before_request_validate", None)
        if before_request_validate:
            validates = before_request_validate(self.step_data.validators)
        else:
            validates = self.step_data.validators

        temp_var = copy.deepcopy(self.case_runner.case_data.config.variables)
        temp_var.update(self.extract_variable)
        for vali in validates:
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
                self.result.status = CaseRunStatus.failed.value
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
        self.parse_request_data()
        if self.before_request(self.step_data.request.model_dump(by_alias=True)) == CaseRunStatus.failed.value:
            return self

        try:
            session_data = SessionData()
            self.result.data = session_data
            req_resps_data = ReqRespData()
            req_resps_data.request = self.step_data.request
            self.result.data.req_resps.append(req_resps_data)

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
                req_resps_data.response = ResponseData(**{"headers": websocket.response_headers,
                                                          "body": res_data,
                                                          "content": res_data,
                                                          "status_code": 200})
                self.response = Response(req_resps_data.response)
            end_time = time.time()
            self.result.duration = round(end_time - start_time, 2)
            if self.step_data.think_time.limit:
                await asyncio.sleep(self.step_data.think_time.limit)
        except Exception as e:
            logger.exception(e)
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
            self.set_step_failed()
            return self

        if self.after_request(self.response) == CaseRunStatus.failed.value:
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


class Result(object):
    def __init__(self, response=None, logs='', name=''):
        self.response: ResponseData = response
        self.request_detail: TRequest | TWebsocket | dict = {}
        self.logs: str = logs
        self.name = name
        self.status = 'passed'
        self.duration = 0
        self.step_id = int(time.time() * 1000)


class TestRunner(object):
    """
    单个用例执行入口，但是执行结果可能是多个用例，例如使用的参数化的情况
    """

    def __init__(self, case_data: TestCase, debugtalk_func_map={}):
        self.parameters = case_data.config.parameters
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
                    before_test_res = before_test(self.case_data.config.variables)
                    if isinstance(before_test_res, dict):
                        self.case_data.config.variables.update(before_test_res)
                    logger.info("before_test处理完成")
                except Exception as e:
                    logger.error(f"before_test处理失败：{e}")
                    logger.exception(e)
                    raise TestFailError(f"before_test处理失败")

            if not self.parameters:
                runner = CaseRunner(self.case_data, self.debugtalk_func_map, self.logger.logger)
                await runner.run()
                data = runner.close_handler()
                return [data]

            params = self.parameters["caseParamters"]
            params = params[1:]

            all_data = []  # 参数化执行时一条用例其实是多条用例，所以需要返回一个列表
            for param in params:
                tmp_case_data = copy.deepcopy(self.case_data)
                tmp_debugtalk_func_map = copy.deepcopy(self.debugtalk_func_map)
                old_variables: dict = tmp_case_data.config.variables
                old_variables.update(param)
                tmp_debugtalk_func_map.update(param)
                tmp_case_data.config.variables = old_variables
                name = tmp_case_data.config.name
                if "case_name" in param:
                    tmp_case_data.config.name = f"{name}[{param['case_name']}]"
                runner = CaseRunner(tmp_case_data, tmp_debugtalk_func_map, self.logger.logger)
                await runner.run()
                data = runner.close_handler()
                all_data.append(data)
            return all_data
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
