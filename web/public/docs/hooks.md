# 关于回调
> 回调不需要返回值，直接修改对应的数据  
> 回调分为默认回调和自定义回调  
> 默认回调：测试执行到对应位置时自动去debugtalk中寻找固定的方法（固定的方法名称）并调用，没找到则不调用且继续测试任务  
> 自定义回调： 自定义方法，并将方法配置到对应位置的hooks设置中


## 回调的执行顺序及参数

| 序号  | 回调实现  | 回调执行位置  | 回调方法                                        |
|-----|-------|---------|---------------------------------------------|
| 1.  | 默认回调  | 开始测试前   | before_test()**[未实现]**                      |
| 2.  | 自定义回调 | 模块执行前   | func()**[未实现]**                             |
| 3.  | 默认回调  | 用例开始执行前 | before_test_case([TestCase](#class-testcasebasemodel))             |
| 4.  | 自定义回调 | 用例执行前   | func([TestCase](#class-testcasebasemodel), **args, ***kwargs) |
| 5.  | 默认回调  | 步骤开始执行前 | before_test_step([TStep](#class-tstepbasemodel))           |
| 6.  | 自定义回调 | 步骤执行前   | func([TStep](#class-tstepbasemodel), **args, ***kwargs)    |
| 7.  | 默认回调  | 校验前的回调  | before_request_validate(List[Dict])         |
| 8.  | 默认回调  | 步骤执行后   | after_test_step([TStep](#class-tstepbasemodel))            |
| 9.  | 自定义回调 | 步骤执行后   | func([TStep](#class-tstepbasemodel), **args, ***kwargs)    |
| 10. | 默认回调  | 用例执行后   | after_test_case([TestCase](#class-testcasebasemodel))      |
| 11. | 自定义回调 | 用例执行后   | func([TestCase](#class-testcasebasemodel), **args, ***kwargs) |
| 12. | 自定义回调 | 模块执行后   | func()**[未实现]**                             |
| 13. | 默认回调  | 测试执行后   | after_test()**[未实现]**                       |


### 自定义回调的使用示例：  

> 自定义回调函数的第一个参数是系统给的默认参数，后面的参数是自己需要传的参数；  
> 自己实现的回调函数至少需要一个参数来接受默认参数，但是在使用的时候默认参数不需要显示写入

>例如自定义的方法为(无自定义参数)：`def test_case_start(test_case)`，至少需要一个参数来接口默认参数TestCase  
使用如下：`${test_case_start()}`，默认参数不需要显示写入  
实际调用会带上默认参数：`test_case_start(test_case)`  
>
>自定义参数：`def test_case_start(test_case, arg1, arg2, arg3=None, arg4=None)`，有三个自定义参数  
使用如下：`${test_case_start(value1, value2, arg4=value4)}`，默认参数不需要显示写入  
实际调用会带上默认参数：`test_case_start(test_case, value1, value2, arg4=value4)`

## 类

### <span id="class-testcasebasemodel">TestCase</span>

##### class TestCase(BaseModel):  
-  case_name: Union[Text, None] = None  
-  module_id: Union[int, None] = None  
-  project_id: Union[int, None] = None  
-  status: Union[int, None] = None  
-  case_id: Any = None  
-  config: [TConfig](#class-tconfigbasemodel)  
-  teststeps: List[[TStep](#class-tstepbasemodel)]  


### <span id="class-tconfigbasemodel">TConfig</span>

##### class TConfig(BaseModel):
- name: Name = ""
- verify: Verify = False
- base_url: BaseUrl = ""
- variables: List[VariablesMapping] | Text = []
- parameters: [ParameterModel](#class-parametermodelbasemodel) | List[VariablesMapping] | None = None
- headers: List[Headers] = []
- setup_hooks: Hooks = []
- teardown_hooks: Hooks = []
- export: Export = []
- path: Text = ""
- db: TConfigDB = TConfigDB()
- think_time: ThinkTime = ThinkTime()
- time_out: TimeOut = TimeOut()
- retry: Retry = Retry()
- include: Union[Include, None] = Include()
- result: Union[[Result](#class-resultbasemodel), None] = Result()


### <span id="class-tstepbasemodel">TStep</span>

##### class TStep(BaseModel):
- name: Name
- step_type: int = TstepTypeEnum.http  # 1 api, 2 webUI
- step_id: Text = ""
- request: Union[[TRequest](#class-trequestbasemodel), [TWebsocket](#class-twebsocketbasemodel), None] = None
- include: Union[Include, None] = Include()
- testcase: Union[Text, Callable, None] = None
- variables: List[VariablesMapping] | Text = []
- setup_hooks: Hooks = []
- teardown_hooks: Hooks = []
- extract: List[VariablesMapping] | Text = []
- export: Export = []
- validators: Validators = Field([], alias="validate")
- validate_script: List[Text] = []
- retry_times: int = 0
- retry_interval: int = 0  # sec
- thrift_request: Union[TThriftRequest, None] = None
- sql_request: Union[TSqlRequest, None] = None
- think_time: ThinkTime = ThinkTime()
- time_out: TimeOut = TimeOut()
- retry: Retry = Retry()
- result: Union[[Result](#class-resultbasemodel), None] = [Result](#class-resultbasemodel)()




### <span id="class-trequestbasemodel">TRequest</span>

##### class TRequest(BaseModel):
- method: MethodEnum
- url: Url
- params: List[Headers] = []
- headers: List[Headers] = []
- req_json: Union[Dict, List, Text, None] = Field(None, alias="json")
- data: List[VariablesMapping] | Text | None = []
- cookies: List[Cookies] = []
- timeout: float | None = 120
- allow_redirects: bool = False
- verify: Verify = False
- upload: Dict = {}  # used for upload files


### <span id="class-twebsocketbasemodel">TWebsocket</span>

##### class TWebsocket(BaseModel):
- url: Url
- params: List[Headers] = []
- headers: List[Headers] = []
- data: Text | None = ""
- cookies: List[Cookies] = []
- timeout: float = 120
- allow_redirects: bool = False
- verify: Verify = False
- recv_num: int = 0  # 消息接受条数，0表示不限制，1表示只接受一条
- result: Union[[Result](#class-resultbasemodel), None] = [Result](#class-resultbasemodel)()


### <span id="class-resultbasemodel">Result</span>

##### class Result(BaseModel):
- success: bool = True
- status: int = CaseRunStatus.passed.value
- start_time_stamp: float = 0
- start_time_iso: str = ""
- end_time_iso: str = ""
- end_time_stamp: float = 0
- duration: float = 0
- response: [ResponseData](#class-responsedatabasemodel) | Text = [ResponseData](#class-responsedatabasemodel)()  # text是用gzip压缩过的数据需要解压
- logs: [StepLogs](#class-stepLogsbasemodel) | Text = [StepLogs](#class-stepLogsbasemodel)()  # text是用gzip压缩过的数据需要解压

### <span id="class-responsedatabasemodel">ResponseData</span>
##### class ResponseData(BaseModel):
- status_code: int = 200
- headers: Dict = {}
- cookies: Cookies = {}
- encoding: Union[Text, None] = None
- content_type: Text = ""
- body: Union[Text, bytes, List, Dict, None] = ""  # 默认不会有值，用于在回调中设置自己转换后的内容
- content: Text | List = ""  # 响应内容为原始数据
- text: Union[Text, None] = ""  # 响应的原始数据转成text的结果

### <span id="class-stepLogsbasemodel">StepLogs</span>
##### class StepLogs(BaseModel):
- before_request: Text = ""
- after_response: Text = ""
- error: Text = ""

### <span id="class-parametermodelbasemodel">ParameterModel</span>
##### class ParameterModel(BaseModel):
- type: int = ParameterTypeEnum.local_table.value
- value: Text = ""