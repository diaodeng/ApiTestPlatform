---
type: contract
source_type: code
---
# 统一凭证接口契约

接口前缀为 `/system/credentials`，响应从不返回凭证明文或密文。认证配置中的请求模板会对密码、Token、Cookie、Authorization 等固定敏感字段脱敏；页面编辑时应使用扁平 `${secret.xxx}` 占位符引用凭证密文，不支持嵌套路径。写入时只提交实际变更的敏感字段，服务端会与原密文合并。`HTTP Header` 类型且 Header 名称为 `Cookie` 的凭证，在刷新模板中使用 `${secret.cookie}` 时会解析为其 Header 值；`${secret.headerValue}` 是直接读取主 Header 值的高级变量，并兼容历史 `header_value`。请求日志会脱敏全部请求 Header、Cookie、Token、Authorization、密码等内容。

数据库旧记录中的认证请求模板、响应映射和目标域名 JSON 字段允许为 `NULL`，接口读取时会分别归一为空对象或空列表，不要求人工回填历史记录。认证配置新增 `loginSuccessAssertions` 和 `refreshSuccessAssertions`，每项使用固定的来源（`status`、`json:`、`header:`、`cookie:`）和操作符，不支持脚本或任意表达式。

认证配置支持 `loginSteps`（多步登录链）与 `refreshSteps`（多步刷新链），元素结构见 `CredentialLoginStepModel`：`id`（可选语义化标识，供 `${step.<id>.变量}` 引用）/`name`/`url`/`method`/`bodyType`（`none`/`form`/`json`/`multipart`，multipart 的 boundary 由服务端生成）/`headers`/`body`/`successAssertions`/`outputs`/`persistOutputs`/`when`（可选条件，变量支持 `step.N.变量`、`step.<id>.变量`、`secret.字段`，不满足时跳过该步骤）。请求模板支持 `${secret.字段}`、`${step.N.变量}` 与 `${step.<id>.变量}`；`outputs` 的来源支持 `json:路径|url_query:参数名`、`json:路径|regex:正则` 一次加工。`persistOutputs=false` 的输出是临时步骤变量（如一次性 ticket），不会写入凭证密文；`persistOutputs=true` 的输出按响应映射规则写回凭证。链配置为空时回退单步模板；`http_login` 自动刷新允许以 `loginSteps` 替代 `loginUrl`，`http_refresh` 自动刷新允许以 `refreshSteps` 替代 `refreshUrl`。

| 接口 | 作用 |
|---|---|
| GET /system/credentials | 查询凭证 |
| POST /system/credentials | 新建凭证并加密 secret |
| PUT /system/credentials/{id} | 按 expectedRevision 更新 |
| POST /system/credentials/{id}/refresh | 手工触发 HTTP 刷新 |
| POST /system/credentials/{id}/test-login-flow | 测试多步登录/刷新链：body 传 `{"flowType":"login|refresh","otpCode":"..."}`，真实执行各步骤并返回逐步明细（状态码、耗时、输出变量名、跳过原因、写回字段名），无论成功与否都不写回凭证密文 |
| /bindings | 管理业务凭证绑定 |
| /binding-options | 获取业务配置下拉项 |
| POST /bindings/{id}/writeback | 在绑定允许、本地缓存启用且版本一致时回写浏览器 storageState |
| GET /operation-logs | 查询脱敏操作审计摘要 |
| GET /leases | 查询当前有效租约摘要 |

`credentialId` 和 `bindingId` 均以字符串返回；业务调用只传 `credentialBindingId`。

日志拉取外部环境不属于统一凭证页面的管理范围，继续使用系统参数 `ticket.logPull.external` 配置；该参数只引用 `credentialBindingId`，认证内容由绑定投影服务解析。

参见：[统一凭证数据模型](../entities/data-models/credential-management.md)、[凭证刷新流程](../flows/credential-refresh.md)。

被引用：统一凭证数据模型、凭证刷新流程。


当主 Header 名称为 `Cookie` 时，响应提取契约拒绝 `cookies` 与 `cookies.名称` 作为目标，调用方应使用 `header.cookie` 或 `header.cookie.名称`。主 Header 不是 `Cookie` 时，结构化 Cookie 目标仍可与 Header 认证共存。
