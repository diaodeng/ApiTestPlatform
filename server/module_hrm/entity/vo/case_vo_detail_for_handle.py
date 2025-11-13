"""
这个是用例数据详情的模型，不是对应于数据库用例表的数据模型，是对应于数据库用例表的request字段的模型
"""
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Text, Union, Annotated

from pydantic import BaseModel, Field, HttpUrl, model_validator, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel

from module_hrm.enums.enums import CaseRunStatus, TstepTypeEnum, ParameterTypeEnum, CodeTypeEnum, ScopeEnum, \
    ConfigDataTypeEnum, AssertOriginalEnum
from module_hrm.utils.common import dict2list

Name = Text
Url = Text
BaseUrl = Union[HttpUrl, Text]
VariablesMapping = Dict[Text, Any]
FunctionsMapping = Dict[Text, Callable]
Headers = Dict[Text, Text | bool | int | float]
Cookies = Dict[Text, Text | bool | int | float]
Verify = bool
Hooks = List[Union[Text, Dict[Text, Any]]]
Export = List[Text]
Validators = List[Dict]


class CodeInfoModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    code_type: int = CodeTypeEnum.js.value
    code_content: str = ""


class HooksModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)

    functions: Hooks = Field(default_factory=lambda: [])
    code_info: CodeInfoModel = CodeInfoModel()

    @model_validator(mode="before")
    def convert_address(cls, values: Dict[str, Any] | list) -> Dict[str, Any]:
        if isinstance(values, list):
            return HooksModel(functions=values).model_dump(by_alias=True)
        return values


class ResponseData(BaseModel):
    status_code: int = 200
    headers: Dict = Field(default_factory=lambda: {})
    cookies: Cookies = Field(default_factory=lambda: {})
    encoding: Union[Text, None] = None
    content_type: Text = ""
    body: Union[Text, bytes, List, Dict, None] = ""  # 默认不会有值，用于在回调中设置自己转换后的内容
    content: Text | List = ""  # 响应内容为原始数据
    text: Union[Text, None] = ""  # 响应的原始数据转成text的结果


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
    response: ResponseData | Text = ResponseData()  # text是用gzip压缩过的数据需要解压
    logs: StepLogs | Text = StepLogs()  # text是用gzip压缩过的数据需要解压


class MethodEnum(Text, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"


class ProtoType(Enum):
    Binary = 1
    CyBinary = 2
    Compact = 3
    Json = 4


class TransType(Enum):
    Buffered = 1
    CyBuffered = 2
    Framed = 3
    CyFramed = 4


# configs for thrift rpc
class TConfigThrift(BaseModel):
    psm: Text = None
    env: Text = None
    cluster: Text = None
    target: Text = None
    include_dirs: List[Text] = None
    thrift_client: Any = None
    timeout: int = 10
    idl_path: Text = None
    method: Text = None
    ip: Text = "127.0.0.1"
    port: int = 9000
    service_name: Text = None
    proto_type: ProtoType = ProtoType.Binary
    trans_type: TransType = TransType.Buffered


# configs for db
class TConfigDB(BaseModel):
    psm: Text = ""
    user: Text = ""
    password: Text = ""
    ip: Text = ""
    port: int = 3306
    database: Text = ""


class TransportEnum(Text, Enum):
    BUFFERED = "buffered"
    FRAMED = "framed"


class TThriftRequest(BaseModel):
    """rpc request model"""

    method: Text = ""
    params: Dict = Field(default_factory=lambda: {})
    thrift_client: Any = None
    idl_path: Text = ""  # idl local path
    timeout: int = 10  # sec
    transport: TransportEnum = TransportEnum.BUFFERED
    include_dirs: List[Union[Text, None]] = Field(default_factory=lambda: [])  # param of thriftpy2.load
    target: Text = ""  # tcp://{ip}:{port} or sd://psm?cluster=xx&env=xx
    env: Text = "prod"
    cluster: Text = "default"
    psm: Text = ""
    service_name: Text = None
    ip: Text = None
    port: int = None
    proto_type: ProtoType = None
    trans_type: TransType = None


class SqlMethodEnum(Text, Enum):
    FETCHONE = "FETCHONE"
    FETCHMANY = "FETCHMANY"
    FETCHALL = "FETCHALL"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class TSqlRequest(BaseModel):
    """sql request model"""

    db_config: TConfigDB = TConfigDB()
    method: SqlMethodEnum = None
    sql: Text = None
    size: int = 0  # limit nums of sql result


class ThinkTime(BaseModel):
    enable: bool = False
    strategy: Text | None = ""
    limit: int | float = 0


class TimeOut(BaseModel):
    enable: bool = False
    limit: int | float = 0


class Retry(BaseModel):
    enable: bool = False
    limit: int = 0
    delay: int = 0


class IncludeConfig(BaseModel):
    id: int | Text | None = None
    name: Text | None = None
    allow_extend: bool = True


class Include(BaseModel):
    config: IncludeConfig = IncludeConfig()


class ParameterModel(BaseModel):
    type: int = ParameterTypeEnum.local_table.value
    value: Text = ""
    is_compress: bool = True


class TConfig(BaseModel):
    name: Name = ""
    verify: Verify = False
    base_url: BaseUrl = ""
    # Text: prepare variables in debugtalk.py, ${gen_variables()}
    variables: List[VariablesMapping] | Text = Field(default_factory=lambda: [])
    parameters: Annotated[Union[ParameterModel, List[VariablesMapping], None], Field(None, description="请求参数")] = None
    headers: List[Headers] = Field(default_factory=lambda: [])
    setup_hooks: HooksModel = HooksModel()
    teardown_hooks: HooksModel = HooksModel()
    export: Export = Field(default_factory=lambda: [])
    path: Text = ""
    # configs for other protocols
    # thrift: TConfigThrift|None = None
    db: TConfigDB = TConfigDB()
    think_time: ThinkTime = ThinkTime()
    time_out: TimeOut = TimeOut()
    retry: Retry = Retry()
    include: Union[Include, None] = Include()
    result: Union[Result, None] = Result()

    @model_validator(mode='before')
    def convert_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # values = CamelCaseUtil.transform_result(values)
        parameters_data = values.get('parameters', None)
        if isinstance(parameters_data, list):
            values["parameters"] = ParameterModel()
        return values


class TRequest(BaseModel):
    """requests.Request model"""

    method: MethodEnum
    url: Url
    params: List[Headers] = Field(default_factory=lambda: [])
    headers: List[Headers] = Field(default_factory=lambda: [])
    req_json: Union[Dict, List, Text, None] = Field(None, alias="json")
    data: List[VariablesMapping] | Text | None = Field(default_factory=lambda: [])
    cookies: List[Cookies] = Field(default_factory=lambda: [])
    timeout: float | None = 120
    allow_redirects: bool = False
    verify: Verify = False
    upload: Dict = Field(default_factory=lambda: {})  # used for upload files

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        request_data = values.get('params', {})
        tmp_headers = values.get('headers', {})
        tmp_data = values.get('data', {})
        tmp_cookies = values.get('cookies', {})
        values['params'] = dict2list(request_data)
        values['headers'] = dict2list(tmp_headers)
        values['data'] = dict2list(tmp_data)
        values['cookies'] = dict2list(tmp_cookies)
        return values


class TStepInclude(BaseModel):
    config_id: Headers = Field(default_factory=lambda: {})  # {"id":1, "name": "configName"}


class TWebsocket(BaseModel):
    """TWebsocket"""
    url: Url
    params: List[Headers] = Field(default_factory=lambda: [])
    headers: List[Headers] = Field(default_factory=lambda: [])
    data: Text | None = ""
    cookies: List[Cookies] = Field(default_factory=lambda: [])
    timeout: float | None = 120
    allow_redirects: bool = False
    verify: Verify = False
    recv_num: int = 0  # 消息接受条数，0表示不限制，1表示只接受一条
    result: Union[Result, None] = Result()

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        request_data = values.get('params', {})
        tmp_headers = values.get('headers', {})
        tmp_cookies = values.get('cookies', {})
        values['params'] = dict2list(request_data)
        values['headers'] = dict2list(tmp_headers)
        values['cookies'] = dict2list(tmp_cookies)
        return values


class ConfigInfo(BaseModel):
    """
    配置表格相关的模型
    """
    key: str = ""
    value: Any = ""
    enable: bool = True
    scope: int = ScopeEnum.case.value
    type: str = ConfigDataTypeEnum.string.value


class StepRunConditionDetail(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    enable: bool = False
    condition_source: Text | int = ""
    loop_var: Text = ""  # 循环过程中的临时变量名
    source_type: Text = ""


class StepRunCondition(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    is_run_info: StepRunConditionDetail = StepRunConditionDetail()
    loop_run_info: StepRunConditionDetail = StepRunConditionDetail()


class TStep(BaseModel):
    name: Name
    step_type: int = TstepTypeEnum.http.value  # 1 api, 2 webUI
    step_id: Text = ""
    enable: bool = True
    run_condition: StepRunCondition = StepRunCondition()
    request: Annotated[Union[TRequest, TWebsocket, None], Field(None, description="请求信息")] = None
    include: Union[Include, None] = Include()
    testcase: Union[Text, Callable, None] = None
    variables: List[VariablesMapping] | Text = Field(default_factory=lambda: [])
    setup_hooks: HooksModel = HooksModel()
    teardown_hooks: HooksModel = HooksModel()
    # used to extract request's response field
    extract: List[VariablesMapping] | Text = Field(default_factory=lambda: [])
    # used to export session variables from referenced testcase
    export: Export = Field(default_factory=lambda: [])
    validators: Validators = Field([], alias="validate")
    validate_script: List[Text] = Field(default_factory=lambda: [])
    retry_times: int = 0
    retry_interval: int = 0  # sec
    thrift_request: Union[TThriftRequest, None] = None
    sql_request: Union[TSqlRequest, None] = None
    think_time: ThinkTime = ThinkTime()
    time_out: TimeOut = TimeOut()
    retry: Retry = Retry()
    result: Union[Result, None] = Result()

    @model_validator(mode="before")
    def convert_data(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        request_data = values.get('request')
        s_type = values.get('step_type')
        if s_type == TstepTypeEnum.http.value:
            if isinstance(request_data, dict):
                values["request"] = TRequest(**request_data).model_dump(by_alias=True)
            else:
                values["request"] = request_data
        elif s_type == TstepTypeEnum.websocket.value:
            if isinstance(request_data, dict):
                values["request"] = TWebsocket(**request_data).model_dump(by_alias=True)
            else:
                values["request"] = request_data
        else:
            values["request"] = request_data

        # 兼容原有抽取数据
        extracts = values.get('extract', [])
        for extract in extracts:
            if not extract.get("scope", None):
                extract["scope"] = ScopeEnum.case.value
        values["extract"] = extracts

        # 兼容原有校验数据
        validates = values.get('validate', [])
        for validate in validates:
            if not validate.get("sourceWay", None):
                validate["sourceWay"] = AssertOriginalEnum.expression.value  # 默认是表达式

        values["validate"] = validates

        return values

    @field_serializer('validators')
    def vali_ser(self, validate: Any):
        """
        吐出去的数据不应是集合对象
        """
        for vali in validate:
            expect = vali.get("expect", "")
            if isinstance(expect, (dict, list, tuple, set)):
                vali["expect"] = json.dumps(expect, ensure_ascii=False)
        return validate


class TestCase(BaseModel):
    case_name: Union[Text, None] = None
    module_id: Union[int, None] = None
    project_id: Union[int, None] = None
    status: Union[int, None] = None  # CaseStatusEnum
    case_id: Any = None
    config: TConfig
    teststeps: List[TStep]


class CustomHooksLogs(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    info: List = Field(default_factory=lambda: [])
    error: List = Field(default_factory=lambda: [])


class CustomHooksParams(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    data: TStep | TestCase | None = None
    globals: dict = Field(default_factory=lambda: {})
    case_variables: dict = Field(default_factory=lambda: {})
    logs: CustomHooksLogs = CustomHooksLogs()
    failed: bool = False
