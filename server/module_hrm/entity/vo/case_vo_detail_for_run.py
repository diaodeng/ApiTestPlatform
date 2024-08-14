"""
这个是用例数据详情的模型，不是对应于数据库用例表的数据模型，是对应于数据库用例表的request字段的模型
"""

import datetime
from typing import Any, Dict, List, Text, Union

from pydantic import BaseModel

from module_hrm.entity.vo import case_vo_detail_for_handle as caseVoHandle
from module_hrm.enums.enums import TstepTypeEnum, CaseRunStatus
from utils.utils import get_platform


class ResponseData(BaseModel):
    status_code: int = 200
    headers: Dict = {}
    cookies: caseVoHandle.Cookies = {}
    encoding: Union[Text, None] = None
    content_type: Text = ""
    body: Union[Text, bytes, List, Dict, None] = ""
    content: Text | List = ""
    text: Union[Text, None] = ""


class StepLogs(BaseModel):
    before_request: Text = ""
    after_response: Text = ""
    error: Text = ""


class Result(BaseModel):
    success: bool = True
    status: int = CaseRunStatus.passed.value
    start_time_stamp: float = 0
    start_time_iso: str = ""
    end_time_iso: str = ""
    end_time_stamp: float = 0
    duration: float = 0
    response: ResponseData = ResponseData()
    logs: StepLogs = StepLogs()


class TConfig(caseVoHandle.TConfig):
    # variables: Union[caseVoHandle.VariablesMapping, Text] = {}
    # parameters: Union[caseVoHandle.VariablesMapping, Text] = {}
    # headers: caseVoHandle.Headers = {}
    result: Union[Result, None] = Result()


class TRequest(caseVoHandle.TRequest):
    """requests.Request model"""

    # params: Dict[Text, Text | int | float | bool | None] = {}
    # headers: caseVoHandle.Headers = {}
    # data: Union[Text, Dict[Text, Any], None] = None
    # cookies: caseVoHandle.Cookies = {}
    pass


class TWebsocket(caseVoHandle.TWebsocket):
    """TWebsocket"""
    # params: caseVoHandle.VariablesMapping = {}
    # headers: caseVoHandle.Headers = {}
    result: Union[Result, None] = Result()
    # cookies: caseVoHandle.Cookies = {}
    recv_num: int = 1  # 消息接受条数，1表示只接受一条


class TStep(caseVoHandle.TStep):
    result: Union[Result, None] = Result()
    # variables: caseVoHandle.VariablesMapping = {}
    # extract: caseVoHandle.VariablesMapping = {}
    # request: Union[TRequest, TWebsocket, None] = None
    # used to export session variables from referenced testcase


class TestCase(caseVoHandle.TestCase):
    module_id: Union[int, None] = None
    project_id: Union[int, None] = None
    case_id: Any = None
    config: TConfig
    teststeps: List[TStep]


class TestCaseTime(BaseModel):
    start_time: float = 0
    end_time: float = 0
    start_time_iso_format: Text = ""
    end_time_iso_format: Text = ""
    duration: float = 0


class TestCaseInOut(BaseModel):
    config_vars: caseVoHandle.VariablesMapping = {}
    export_vars: Dict = {}


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
    req_resps: List[ReqRespData] = []
    stat: RequestStat = RequestStat()
    address: AddressData = AddressData()
    validators: Dict = {}


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
    export_vars: caseVoHandle.VariablesMapping = {}
    log: Text = ""
    attachment: Text = ""  # teststep attachment


StepResult.update_forward_refs()


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
    log: Dict[Text, Any] = {}
    step_results: List[StepResult] = []


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
    status_items: List[str] = [st.name for st in CaseRunStatus]
    platform: Dict = get_platform()
    start_time: str = ''
    results: List[Dict] = []
    status_count: Dict[str, int] | CaseRunResultCount = {}


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
