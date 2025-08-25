# 关于回调
> 回调不需要返回值，直接修改对应的数据  
> 回调分为默认回调和自定义回调，如果默认回调  
> 默认回调：测试执行到对应位置时自动去debugtalk中寻找固定的方法（固定的方法名称）并调用，没找到则不调用且继续测试任务  
> 自定义回调： 自定义方法，并将方法配置到对应位置的hooks设置中


## 回调的执行顺序及参数

| 序号  | 回调实现  | 回调执行位置  | 回调方法                                                          |
|-----|-------|---------|---------------------------------------------------------------|
| 1.  | 默认回调  | 开始测试前   | before_test()**[未实现]**                                        |
| 2.  | 自定义回调 | 模块执行前   | func()**[未实现]**                                               |
| 3.  | 默认回调  | 用例开始执行前 | before_test_case([TestCase](#class-testcasebasemodel))        |
| 4.  | 自定义回调 | 用例执行前   | func([TestCase](#class-testcasebasemodel), **args, ***kwargs) |
| 5.  | 默认回调  | 步骤开始执行前 | before_test_step([TStep](#class-tstepbasemodel))              |
| 6.  | 自定义回调 | 步骤执行前   | func([TStep](#class-tstepbasemodel), **args, ***kwargs)       |
| 7.  | 自定义脚本 | 步骤执行前   | func([CustomHooksParams](#class-CustomHooksParams))       |
| 8.  | 执行请求  | 执行请求    | 执行步骤中配置的请求                                                    |
| 9.  | 默认回调  | 校验前的回调  | before_request_validate(List[Dict])                           |
| 10. | 默认回调  | 步骤执行后   | after_test_step([TStep](#class-tstepbasemodel))               |
| 11. | 自定义回调 | 步骤执行后   | func([TStep](#class-tstepbasemodel), **args, ***kwargs)       |
| 12. | 自定义脚本 | 步骤执行后   | func([CustomHooksParams](#class-CustomHooksParams))       |
| 13. | 默认回调  | 用例执行后   | after_test_case([TestCase](#class-testcasebasemodel))         |
| 14. | 自定义回调 | 用例执行后   | func([TestCase](#class-testcasebasemodel), **args, ***kwargs) |
| 15. | 自定义回调 | 模块执行后   | func()**[未实现]**                                               |
| 16. | 默认回调  | 测试执行后   | after_test()**[未实现]**                                         |


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


### <span id="class-CustomHooksParams">CustomHooksParams</span>

##### class CustomHooksParams(BaseModel):
- data: [TStep](#class-tstepbasemodel) | [TestCase](class-testcasebasemodel) | None = None
- globals: dict = Field(default_factory=lambda: {})
- case_variables: dict = Field(default_factory=lambda: {})


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

## 自定义脚本中可以使用的内容
js脚本
> 直接从apt中取用对应数据，apt对应的是CustomHooksParams对象
```js
logInfo("来至于测试环境的");  // info日志
logError("错误日志");  // 错误日志
console.log("很好，正常日志");  // info日志


assert(1<2, "断言成功", "测试失败了哈1");  // 断言，前面是成功的信息，后面是失败的信息
assert(1<3, "断言成功", "测试失败了哈2");
assert(1==1, "断言成功", "测试成功了哈3");

// throw new Error("Something went wrong!");


var test9 = jmespath.search({a:"jmespathvalue",b:2}, "a");  // 使用jmespath提取内容
apt.caseVariables.test111 = test9;  // 在用例作用域的变量池中增加变量test111

apt.data.request.params.D = test9;  // 修改请求参数中D的值为test9变量对应的值

apt.globals.step1HookGv = "global_hook_var";  // 向全局变量池中增加或修改变量step1HookGv
apt.caseVariables.step1HookCv = "case_hook_var";  // 向用例范围的变量池中增加或修改变量step1HookCv

apt.data.request.params.C = 999999999999;

var cities = [
  { name: "London", "population": 8615246 },
  { name: "Berlin", "population": 3517424 },
  { name: "Madrid", "population": 3165235 },
  { name: "Rome",   "population": 2870528 }
];

var names = jsonpath.query(cities, '$..name');  //使用jsonpath提取内容
apt.caseVariables.names = names;

apt.data.request.params.E = names[0];


```

python脚本
> 直接从apt中取用对应数据，apt对应的是CustomHooksParams对象
```python
assertC(1<2, "1", "2");  # 断言，前面是成功的信息，后面是失败的信息
assertC(1<2, "1", "2");  
logger.info("正常信息");  # info日志
logger.error("异常信息");  # 错误日志


jsonpath({"a":"jsonpathvalue","b":2}, "$.a")  # 使用jsonpath提取内容
jmespath.search("a", {"a":"jmespathvalue","b":2})  # 使用jmespath提取内容

apt.globals["step1_hook_gv"] = "1111111"  # 设置全局变量
stepResponseCode = apt.data.result.response.status_code
stepResponseText = apt.data.result.response.text

apt.globals["stepResponseText"] = apt.data.result.response.text

apt.globals["case_hook_var3"] = json.loads(stepResponseText)["data"].get("1234")  # 将结果中的值设置到全局变量

#apt.globals["case_hook_var3"] = "990099"


```