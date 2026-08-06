---
type: contract
source_type: code
---
# 统一凭证接口契约

接口前缀为 `/system/credentials`，响应从不返回凭证明文或密文。认证配置中的请求模板会对密码、Token、Cookie、Authorization 等固定敏感字段脱敏；页面编辑时应使用 `${secret.xxx}` 占位符引用凭证密文。写入时只提交实际变更的敏感字段，服务端会与原密文合并。

数据库旧记录中的认证请求模板、响应映射和目标域名 JSON 字段允许为 `NULL`，接口读取时会分别归一为空对象或空列表，不要求人工回填历史记录。

| 接口 | 作用 |
|---|---|
| GET /system/credentials | 查询凭证 |
| POST /system/credentials | 新建凭证并加密 secret |
| PUT /system/credentials/{id} | 按 expectedRevision 更新 |
| POST /system/credentials/{id}/refresh | 手工触发 HTTP 刷新 |
| /bindings | 管理业务凭证绑定 |
| /binding-options | 获取业务配置下拉项 |
| POST /bindings/{id}/writeback | 在绑定允许、本地缓存启用且版本一致时回写浏览器 storageState |
| GET /operation-logs | 查询脱敏操作审计摘要 |
| GET /leases | 查询当前有效租约摘要 |

`credentialId` 和 `bindingId` 均以字符串返回；业务调用只传 `credentialBindingId`。

日志拉取外部环境不属于统一凭证页面的管理范围，继续使用系统参数 `ticket.logPull.external` 配置；该参数只引用 `credentialBindingId`，认证内容由绑定投影服务解析。

参见：[统一凭证数据模型](../entities/data-models/credential-management.md)、[凭证刷新流程](../flows/credential-refresh.md)。

被引用：统一凭证数据模型、凭证刷新流程。
