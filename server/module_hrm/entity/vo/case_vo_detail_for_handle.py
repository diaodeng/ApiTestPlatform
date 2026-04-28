"""
这个是用例数据详情的模型，不是对应于数据库用例表的数据模型，是对应于数据库用例表的request字段的模型
"""
import json
from collections.abc import Callable
from enum import Enum
from typing import Annotated, Any, Dict, List, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, model_validator
from pydantic.alias_generators import to_camel

from module_hrm.enums.enums import (
    AssertOriginalEnum,
    CaseRunStatus,
    CodeTypeEnum,
    ConfigDataTypeEnum,
    ParameterTypeEnum,
    ScopeEnum,
    TstepTypeEnum,
)
from module_hrm.entity.vo.run_error_vo import RunErrorEventModel
from module_hrm.utils.common import dict2list

Name = str
Url = str
BaseUrl = Union[HttpUrl, str]
VariablesMapping = Dict[str, Any]
FunctionsMapping = Dict[str, Callable]
Headers = Dict[str, str | bool | int | float]
Cookies = Dict[str, str | bool | int | float]
Verify = bool
Hooks = List[Union[str, Dict[str, Any]]]
Export = List[str]
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
    encoding: Union[str, None] = None
    content_type: str = ""
    body: Union[str, bytes, List, Dict, None] = ""  # 默认不会有值，用于在回调中设置自己转换后的内容
    content: str | List = ""  # 响应内容为原始数据
    text: Union[str, None] = ""  # 响应的原始数据转成text的结果


class StepLogs(BaseModel):
    before_request: str = ""
    after_response: str = ""
    error: str = ""


class Result(BaseModel):
    success: bool = True
    status: int = CaseRunStatus.passed.value
    start_time_stamp: float = 0
    start_time_iso: str = ""
    end_time_iso: str = ""
    end_time_stamp: float = 0
    duration: float = 0
    response: ResponseData | str = ResponseData()  # text是用gzip压缩过的数据需要解压
    logs: StepLogs | str = StepLogs()  # text是用gzip压缩过的数据需要解压
    error_events: List[RunErrorEventModel] = Field(default_factory=list)


class MethodEnum(str, Enum):
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
    psm: str = None
    env: str = None
    cluster: str = None
    target: str = None
    include_dirs: List[str] = None
    thrift_client: Any = None
    timeout: int = 10
    idl_path: str = None
    method: str = None
    ip: str = "127.0.0.1"
    port: int = 9000
    service_name: str = None
    proto_type: ProtoType = ProtoType.Binary
    trans_type: TransType = TransType.Buffered


# configs for db
class TConfigDB(BaseModel):
    psm: str = ""
    user: str = ""
    password: str = ""
    ip: str = ""
    port: int = 3306
    database: str = ""


class TransportEnum(str, Enum):
    BUFFERED = "buffered"
    FRAMED = "framed"


class TThriftRequest(BaseModel):
    """rpc request model"""

    method: str = ""
    params: Dict = Field(default_factory=lambda: {})
    thrift_client: Any = None
    idl_path: str = ""  # idl local path
    timeout: int = 10  # sec
    transport: TransportEnum = TransportEnum.BUFFERED
    include_dirs: List[Union[str, None]] = Field(default_factory=lambda: [])  # param of thriftpy2.load
    target: str = ""  # tcp://{ip}:{port} or sd://psm?cluster=xx&env=xx
    env: str = "prod"
    cluster: str = "default"
    psm: str = ""
    service_name: str = None
    ip: str = None
    port: int = None
    proto_type: ProtoType = None
    trans_type: TransType = None


class SqlMethodEnum(str, Enum):
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
    sql: str = None
    size: int = 0  # limit nums of sql result


class ThinkTime(BaseModel):
    enable: bool = False
    strategy: str | None = ""
    limit: int | float = 0


class TimeOut(BaseModel):
    enable: bool = False
    limit: int | float = 0


class Retry(BaseModel):
    enable: bool = False
    limit: int = 0
    delay: int = 0


class IncludeConfig(BaseModel):
    id: int | str | None = None
    name: str | None = None
    allow_extend: bool = True


class Include(BaseModel):
    config: IncludeConfig = IncludeConfig()


class ParameterModel(BaseModel):
    type: int = ParameterTypeEnum.local_table.value
    value: str = ""
    is_compress: bool = True


class TConfig(BaseModel):
    name: Name = ""
    verify: Verify = False
    base_url: BaseUrl = ""
    # Text: prepare variables in debugtalk.py, ${gen_variables()}
    variables: List[VariablesMapping] | str = Field(default_factory=lambda: [])
    parameters: Annotated[Union[ParameterModel, List[VariablesMapping], None], Field(None, description="请求参数")] = None
    headers: List[Headers] = Field(default_factory=lambda: [])
    setup_hooks: HooksModel = HooksModel()
    teardown_hooks: HooksModel = HooksModel()
    export: Export = Field(default_factory=lambda: [])
    path: str = ""
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
    req_json: Union[Dict, List, str, None] = Field(None, alias="json")
    data: List[VariablesMapping] | str | None = Field(default_factory=lambda: [])
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
    data: str | None = ""
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
    condition_source: str | int = ""
    loop_var: str = ""  # 循环过程中的临时变量名
    source_type: str = ""


class StepRunCondition(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True)
    is_run_info: StepRunConditionDetail = StepRunConditionDetail()
    loop_run_info: StepRunConditionDetail = StepRunConditionDetail()


class TStep(BaseModel):
    name: Name
    step_type: int = TstepTypeEnum.http.value  # 1 api, 2 webUI
    step_id: str = ""
    enable: bool = True
    run_condition: StepRunCondition = StepRunCondition()
    request: Annotated[Union[TRequest, TWebsocket, None], Field(None, description="请求信息")] = None
    include: Union[Include, None] = Include()
    testcase: Union[str, Callable, None] = None
    variables: List[VariablesMapping] | str = Field(default_factory=lambda: [])
    setup_hooks: HooksModel = HooksModel()
    teardown_hooks: HooksModel = HooksModel()
    # used to extract request's response field
    extract: List[VariablesMapping] | str = Field(default_factory=lambda: [])
    # used to export session variables from referenced testcase
    export: Export = Field(default_factory=lambda: [])
    validators: Validators = Field([], alias="validate")
    validate_script: List[str] = Field(default_factory=lambda: [])
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
    case_name: Union[str, None] = None
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
    error_events: List[RunErrorEventModel] = Field(default_factory=list)
