import copy
import json
import os.path
import time

import jmespath
import requests

from module_hrm.entity.vo.case_vo_detail_for_run import TestCase, TConfig, TStep, TRequest
from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum
from module_hrm.exceptions import TestFailError
from module_hrm.utils import debugtalk_common, comparators
from module_hrm.utils.CaseRunLogHandle import log_context, RunLogCaptureHandler, TestLog
from module_hrm.utils.parser import parse_data
from module_hrm.utils.util import replace_variables, compress_text, get_func_map, ensure_str, load_csv_file_to_test
from utils.log_util import logger


class CaseRunner(object):
    def __init__(self, case_data: TestCase, debugtalk_func_map={}, logger=None):
        self.case_data = case_data
        self.logger = logger
        self.handler = RunLogCaptureHandler()
        self.logger.addHandler(self.handler)

        self.status = CaseRunStatus.passed.value
        self.duration = 0
        # self.request = None
        self.response: list[requests.Response] = []
        self.logs: list[str] = []
        self.results: list[Result] = []
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

    def run(self):
        start_info = f"{'>>>开始执行用例：' + self.case_data.config.name:>^100}"
        logger.info(start_info)
        self.logger.info(start_info)
        start_time = time.time()
        for step in self.case_data.teststeps:
            step_type = step.step_type
            if step_type == TstepTypeEnum.api.value:
                # TODO 测试步骤根据不同请求类型做不同处理
                pass

            tem_step_variable_str = json.dumps(step.variables)
            new_step_variables = json.loads(parse_data(tem_step_variable_str,
                                                       self.case_data.config.variables,
                                                       self.debugtalk_func_map
                                                       ))
            step.variables = new_step_variables

            tmp_config_variables = copy.deepcopy(self.case_data.config.variables)
            tmp_config_variables.update(new_step_variables)

            # 处理json变量，如果整体都是变量直接替换后再json.loads会报错
            json_data = step.request.json
            if isinstance(json_data, str):
                json_data_parsed = parse_data(json_data, tmp_config_variables, self.debugtalk_func_map)
                json_data_obj = json.loads(json_data_parsed)
                step.request.json = json_data_obj

            # 发起请求
            step_obj = Request(self, step).request().validate()
            log_content = self.handler.get_log()
            step_obj.result.logs = compress_text(log_content)
            if step_obj.result.status == CaseRunStatus.failed.value:
                self.status = CaseRunStatus.failed.value

            self.case_data.config.variables.update(step_obj.extract_variable)
            self.response.append(step_obj.response)
            self.results.append(step_obj.result)

            del step_obj.debugtalk_func_map
        end_info = f"{'执行结束用例：' + self.case_data.config.name + '<<<':<^100}"
        logger.info(end_info)
        self.logger.info(end_info)
        del self.debugtalk_func_map
        end_time = time.time()
        self.duration = round(end_time - start_time, 2)
        return self


class RequestConfig(object):
    def __init__(self, config_data):
        tem_config = json.dumps(config_data)
        tem_variables = config_data.get("variables", {})
        new_config = json.loads(replace_variables(tem_config, tem_variables))

        self.variables: dict = new_config.get("variables", {})
        self.base_url: str = new_config.get("base_url", None)
        self.case_name: str = new_config.get("name", "用例名")


class Request(object):
    def __init__(self, case_runner: CaseRunner, step_data: TStep):
        self.logger = case_runner.logger
        self.case_runner = case_runner
        self.debugtalk_func_map = case_runner.debugtalk_func_map
        self.__request_data: TRequest = step_data.request
        self.method = self.__request_data.method.upper()
        self.url = self.__request_data.url
        if not self.url.startswith("http"):
            self.url = self.case_runner.case_data.config.base_url + self.url
        self.files = None
        self.variables = step_data.variables
        self.extract = step_data.extract
        self.step_name = step_data.name
        self.validates = step_data.validators
        self.response: requests.Response = None
        self.extract_variable: dict = {}
        self.result: Result = Result()

    def __step_failed(self):
        self.result.status = CaseRunStatus.failed.value
        self.case_runner.status = CaseRunStatus.failed.value

    def request(self):
        request_data: TRequest = self.__request_data.model_dump(by_alias=True)

        request_data = parse_data(request_data,
                                  self.case_runner.case_data.config.variables,
                                  self.debugtalk_func_map)

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

        # 请求前的回调
        before_request = self.debugtalk_func_map.get("before_request", None)
        if before_request:
            try:
                request_data = before_request(request_data)
                request_data = parse_data(request_data,
                                          self.case_runner.case_data.config.variables,
                                          self.debugtalk_func_map)
            except Exception as e:
                self.__step_failed()
                self.logger.error(f"before_request函数执行失败: {e}")
                return self

        logger.info(f'{">>>请求:" + self.step_name:=^100}')
        self.logger.info(f'{">>>请求:" + self.step_name:=^100}')
        logger.info(f"url: {self.url}")
        self.logger.info(f"url: {self.url}")
        logger.info(f"method: {self.method}")
        self.logger.info(f"method: {self.method}")
        logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")
        self.logger.info(f"Request: {json.dumps(request_data, indent=4, ensure_ascii=False)}")

        try:
            start_time = time.time()
            self.response = requests.request(**request_data)
            end_time = time.time()
            self.result.duration = round(end_time - start_time, 2)
        except Exception as e:
            logger.exception(e)
            self.logger.error(f'error:{json.dumps({"args": str(e.args), "msg": str(e)}, indent=4, ensure_ascii=False)}')
            self.response = None
            self.result.response = self.response
            self.result.name = self.step_name
            self.result.status = CaseRunStatus.failed.value
            self.__step_failed()
            return self

        # 响应回调
        try:
            after_request = self.debugtalk_func_map.get("after_request", None)
            if after_request:
                after_request(self.response)
        except Exception as ef:
            self.__step_failed()
            logger.exception(ef)
            self.logger.info(f"response.text: {self.response.text}")
            self.logger.error(
                f'回调after_request处理异常，error:{json.dumps({"args": str(ef.args), "msg": str(ef)}, indent=4, ensure_ascii=False)}')
            return self

        self.extract_data()

        logger.info(f'request.headers: {json.dumps(dict(self.response.request.headers), indent=4, ensure_ascii=False)}')
        self.logger.info(
            f'request.headers: {json.dumps(dict(self.response.request.headers), indent=4, ensure_ascii=False)}')
        logger.info(f'request.body: {self.response.request.body}')
        self.logger.info(f'request.body: {ensure_str(self.response.request.body)}')

        logger.info(f'{"<<<请求结果:" + self.step_name:=^100}')
        self.logger.info(f'{"<<<请求结果:" + self.step_name:=^100}')
        logger.info(f'status_code: {self.response.status_code}')
        self.logger.info(f'status_code: {self.response.status_code}')
        logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        self.logger.info(f'response.headers: {json.dumps(dict(self.response.headers), indent=4, ensure_ascii=False)}')
        logger.info(f'response.text: {self.response.text}')
        self.logger.info(f'response.body: {self.response.body if hasattr(self.response, "body") else self.response.text}')
        logger.info(f'{"请求:" + self.step_name + "<<<":=^100}')
        self.logger.info(f'{"请求:" + self.step_name + "<<<":=^100}')

        # self.result = Result(self.response, compress_text(self.logs), name=self.step_name)
        self.result.response = self.response
        self.result.name = self.step_name

        return self

    def extract_data(self):
        """
        从请求响应中提取变量
        """
        try:
            res_json = self.response.json()
            for key in self.extract:
                va = ".".join(self.extract[key].strip().split(".")[1:])  # 为了兼容hr，抽取的jmsepath路劲前有data/body/json等字样需要去掉
                val = jmespath.search(va, res_json)
                self.extract_variable[key] = val
            logger.info(f'{self.step_name} extract_variable: {self.extract_variable}')
            self.logger.info(f'{self.step_name} extract_variable: {json.dumps(self.extract_variable)}')
            return self
        except Exception as e:
            self.__step_failed()
            logger.error("提取变量失败")
            logger.error(e)
            self.logger.error(f'{self.step_name} 提取变量失败\n {e}')
            self.result.status = CaseRunStatus.failed.value

    def validate(self):
        # 校验数据处理回调

        before_request_validate = self.debugtalk_func_map.get("before_request_validate", None)
        if before_request_validate:
            validates = before_request_validate(self.validates)
        else:
            validates = self.validates

        for vali in validates:
            assert_key = vali["assert"]
            assert_key = parse_data(assert_key, self.case_runner.case_data.config.variables, self.debugtalk_func_map)
            check_key = vali["check"]
            check_key: str = parse_data(check_key, self.case_runner.case_data.config.variables, self.debugtalk_func_map)
            expect = vali["expect"]
            expect = parse_data(expect, self.case_runner.case_data.config.variables, self.debugtalk_func_map)

            assert_expression = f'{assert_key}({check_key}, {expect})'
            msg = vali.get("msg", assert_expression)
            msg = parse_data(msg, self.case_runner.case_data.config.variables, self.debugtalk_func_map)

            func = self.debugtalk_func_map.get(assert_key, None)  # 自定义断言方法
            if not func and hasattr(comparators, assert_key):
                func = getattr(comparators, assert_key)

            if not func:
                self.logger.error(f'断言方法【{assert_key}】未找到方法')
                self.__step_failed()
                return self
                # raise AttributeError(f'未找到方法：{vali["assert"]}')

            try:
                func(self.__get_validate_key(check_key), expect, msg)
                self.logger.info(f'断言成功，{assert_key}({check_key}, {expect}, {msg})')
            except Exception as e:
                logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')
                logger.exception(e)
                self.__step_failed()
                # self.logger.error(f'{e}')
                self.logger.error(f'断言失败：{assert_key}({check_key}, {expect}, {msg})')

                self.logger.exception(e)
                self.result.status = CaseRunStatus.failed.value
                continue
            self.logger.info("\n")

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
        else:
            par_data = jmespath.search(key, self.response.json())

        if not isinstance(par_data, str):
            par_data = json.dumps(par_data, ensure_ascii=False)
        return par_data


class Result(object):
    def __init__(self, response=None, logs='', name=''):
        self.response: requests.Response = response
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

    def start(self) -> list[CaseRunner]:
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
                data = CaseRunner(self.case_data, self.debugtalk_func_map, self.logger.logger).run().close_handler()
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
                data = CaseRunner(tmp_case_data, tmp_debugtalk_func_map, self.logger.logger).run().close_handler()
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
