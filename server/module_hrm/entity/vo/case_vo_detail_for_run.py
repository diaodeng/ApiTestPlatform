"""
这个是用例数据详情的模型，不是对应于数据库用例表的数据模型，是对应于数据库用例表的request字段的模型
"""

import datetime
from typing import Any, Dict, List, Text, Union

from pydantic import BaseModel, model_validator, Field

from module_hrm.entity.vo import case_vo_detail_for_handle as caseVoHandle
from module_hrm.enums.enums import TstepTypeEnum, CaseRunStatus
from module_hrm.utils.common import key_value_dict
from utils.utils import get_platform


class ResponseData(caseVoHandle.ResponseData):
    pass


class StepLogs(caseVoHandle.StepLogs):
    pass


class Result(caseVoHandle.Result):
    pass


class TConfig(caseVoHandle.TConfig):
    # variables: Union[caseVoHandle.VariablesMapping, Text] = Field(default_factory=lambda: {})
    # parameters: Union[caseVoHandle.VariablesMapping, Text] = Field(default_factory=lambda: {})
    # headers: caseVoHandle.Headers = Field(default_factory=lambda: {})
    result: Union[Result, None] = Result()


class TRequest(caseVoHandle.TRequest):
    """requests.Request model"""

    params: Dict[Text, Text | int | float | bool | None] = Field(default_factory=lambda: {})
    headers: caseVoHandle.Headers = Field(default_factory=lambda: {})
    data: Union[Text, Dict[Text, Any], None] = None
    cookies: caseVoHandle.Cookies = Field(default_factory=lambda: {})

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        request_data = values.get('params', {})
        tmp_headers = values.get('headers', {})
        tmp_data = values.get('data', {})
        tmp_cookies = values.get('cookies', {})
        values['params'] = key_value_dict(request_data)
        values['headers'] = key_value_dict(tmp_headers)
        values['data'] = key_value_dict(tmp_data)
        values['cookies'] = key_value_dict(tmp_cookies)
        return values


class TWebsocket(caseVoHandle.TWebsocket):
    """TWebsocket"""
    # params: caseVoHandle.VariablesMapping = Field(default_factory=lambda: {})
    # headers: caseVoHandle.Headers = Field(default_factory=lambda: {})
    params: Dict[Text, Text | int | float | bool | None] = Field(default_factory=lambda: {})
    headers: caseVoHandle.Headers = Field(default_factory=lambda: {})
    data: Union[Text, Dict[Text, Any], None] = None
    cookies: caseVoHandle.Cookies = Field(default_factory=lambda: {})
    result: Union[Result, None] = Result()
    # cookies: caseVoHandle.Cookies = Field(default_factory=lambda: {})
    recv_num: int = 1  # 消息接受条数，1表示只接受一条

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        request_data = values.get('params', {})
        tmp_headers = values.get('headers', {})
        tmp_cookies = values.get('cookies', {})
        values['params'] = key_value_dict(request_data)
        values['headers'] = key_value_dict(tmp_headers)
        values['cookies'] = key_value_dict(tmp_cookies)
        return values


class TStep(caseVoHandle.TStep):
    result: Union[Result, None] = Result()
    request: Union[TRequest, TWebsocket, None] = None



class TestCase(caseVoHandle.TestCase):
    pass


class TestCaseTime(BaseModel):
    start_time: float = 0
    end_time: float = 0
    start_time_iso_format: Text = ""
    end_time_iso_format: Text = ""
    duration: float = 0


class TestCaseInOut(BaseModel):
    config_vars: caseVoHandle.VariablesMapping = Field(default_factory=lambda: {})
    export_vars: Dict = Field(default_factory=lambda: {})


class RequestStat(BaseModel):
    content_size: float = 0
    response_time_ms: float = 0
    elapsed_ms: float = 0


class AddressData(BaseModel):
    client_ip: Text = "N/A"
    client_port: int = 0
    server_ip: Text = "N/A"
    server_port: int = 0


class ReqRespData(BaseModel):
    request: TRequest | TWebsocket | None = None
    response: ResponseData | None = None


class SessionData(BaseModel):
    """request session data, including request, response, validators and stat data"""

    success: bool = False
    # in most cases, req_resps only contains one request & response
    # while when 30X redirect occurs, req_resps will contain multiple request & response
    req_resps: List[ReqRespData] = Field(default_factory=lambda: [])
    stat: RequestStat = RequestStat()
    address: AddressData = AddressData()
    validators: Dict = Field(default_factory=lambda: {})


class StepResult(BaseModel):
    """teststep data, each step maybe corresponding to one request or one testcase"""

    name: Text = ""  # teststep name
    step_type: int = TstepTypeEnum.http.value  # teststep type
    step_id: Text | int = ""  # teststep id
    success: bool = True
    duration: float = 0.0  # teststep duration
    status: Text = CaseRunStatus.passed.value
    data: Union[SessionData, List["StepResult"]] = None
    elapsed: float = 0.0  # teststep elapsed time
    content_size: float = 0  # response content size
    export_vars: caseVoHandle.VariablesMapping = Field(default_factory=lambda: {})
    log: Text = ""
    attachment: Text = ""  # teststep attachment


StepResult.model_rebuild()


class IStep(object):
    def name(self) -> str:
        raise NotImplementedError

    def type(self) -> str:
        raise NotImplementedError

    def struct(self) -> TStep:
        raise NotImplementedError

    def run(self, runner) -> StepResult:
        # runner: HttpRunner
        raise NotImplementedError


class TestCaseSummary(BaseModel):
    name: Text
    success: bool = True
    status: int = CaseRunStatus.passed.value
    case_id: Text | int | None = None
    time: TestCaseTime = TestCaseTime()
    in_out: TestCaseInOut = TestCaseInOut()
    log: Dict[Text, Any] = Field(default_factory=lambda: {})
    step_results: List[StepResult] = Field(default_factory=lambda: [])


class PlatformInfo(BaseModel):
    httprunner_version: Text
    python_version: Text
    platform: Text


class Stat(BaseModel):
    total: int = 0
    success: int = 0
    fail: int = 0


class TestSuiteSummary(BaseModel):
    success: bool = False
    stat: Stat = Stat()
    time: TestCaseTime = TestCaseTime()
    platform: PlatformInfo
    testcases: List[TestCaseSummary]


"""
============================
测试报告相关
============================
"""


class CaseRunResultCount(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0


class ReportDtailToView(BaseModel):
    """
    测试报告用于前端显示的模型
    """
    exitstatus: int = 0
    status_items: List[str] = Field(default_factory=lambda: [st.name for st in CaseRunStatus])
    platform: Dict = Field(default_factory=lambda: get_platform())
    start_time: str = ''
    results: List[Dict] = Field(default_factory=lambda: [])
    status_count: Dict[str, int] | CaseRunResultCount = Field(default_factory=lambda: {})


class ReportInfo(BaseModel):
    """
    测试报告入库数据模型
    """
    name: str = "",
    status: bool = False,
    successes: int = 0,  # 成功case数量
    test_run: int = 0,  # 执行case总数
    run_test_time: str = datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S"),  # 开始执行的时间,
    report_path: str = "",  # 报告路径
    report_id: Any = None,  # 报告ID
    type: str = 'html'
