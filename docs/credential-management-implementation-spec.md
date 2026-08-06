# 统一凭证管理模块实施规格

> 文档用途：本文件是统一凭证管理功能的实施基线，供后续模型或开发人员直接执行。除非用户明确修改本文件中的约束，否则实现、重构、测试和验收都应以本文件为准。
>
> 方案状态：最终确认方案。旧凭证数据不迁移，由用户在新模块中重新创建和绑定。

## 1. 背景与目标

项目中存在多种外部认证信息：HTTP Header、Cookie、Authorization、Token、API Key，以及浏览器登录后的 Playwright `storageState`。这些信息过去分散在业务配置、浏览器 Session、Runtime Profile 或内联 Header 中，导致：

- 凭证明文散落在多个业务配置中，无法集中管理；
- HTTP 接口和 Web 自动化各自维护认证状态，难以统一刷新和失效判断；
- 同一凭证可能被多个任务同时刷新或使用，容易产生版本覆盖和登录失效；
- 业务需要知道凭证的具体格式，无法只依赖一个稳定的凭证引用；
- 手工登录后得到的浏览器状态无法自然沉淀为可复用凭证。

最终目标是新增独立的统一凭证管理模块，作为 Cookie、Session、Authorization、Token、API Key 和浏览器 `storageState` 的唯一事实源。业务只保存凭证绑定 ID，调用时由凭证模块把密文投影为目标调用方式。

```text
业务配置
  -> credentialBindingId
  -> 凭证绑定
  -> 凭证密文解析
  -> HTTP Header / Cookie / Playwright storageState 投影
```

凭证管理模块负责维护凭证的可用性；业务模块只负责声明“使用哪个绑定”和“以什么业务场景使用”，不负责自行保存、刷新或回写凭证明文。

## 2. 明确范围和不做事项

### 2.1 本次必须实现

- 新增独立凭证、认证配置、业务绑定、操作日志、租约相关数据表；
- 支持手工录入、HTTP 登录、HTTP 刷新、浏览器登录、浏览器刷新等认证方式；
- 支持 HTTP Header、HTTP Cookie、Playwright `storageState` 三类投影；
- 支持共享读取、独占刷新、独占使用三类并发策略；
- 支持按绑定选择凭证，并在 HTTP 请求时将 Session 类凭证投影成 Cookie/Header；
- 支持定时任务判断凭证是否需要刷新，并只更新确实发生变化的凭证；
- 支持 HTTP 工单日志拉取通过绑定解析 Header/Cookie；
- 保留远端工单同步，当前按 API Key 或固定 Header 使用，不默认刷新；
- 支持 Web 执行选择 `web_case` 类型的 `playwright_storage` 绑定；
- 保留录制过程中手工登录，录制结束时自动创建浏览器凭证并保存；
- 保留客户端本地浏览器状态缓存，但普通执行默认不回写服务端凭证；
- 支持显式配置“允许回写凭证”，并且只有启用本地缓存时才允许客户端最终状态回写。

### 2.2 明确不做

- 不迁移任何旧凭证数据。旧数据由用户自行重新创建和配置；
- 不保留旧 Browser Session、Runtime Profile API 和数据模型的兼容入口；
- 不保留普通 Web 执行自动回写服务端凭证的默认行为；
- 不删除远端工单同步功能；
- 不要求系统判断日志平台和 Web 平台是否共用认证系统。用户配置同一个凭证即表示共用，配置不同凭证即表示隔离；
- 不强行把所有站点都改造成 HTTP 登录。具体凭证由用户配置其实际认证特性；
- 不在统一凭证管理页面提供日志拉取外部接口环境的可视化编辑；该配置暂时继续通过系统参数 `ticket.logPull.external` 维护；
- 不把 OTP 交互伪装成系统可自动完成的能力。能否自动化取决于 OTP 类型和用户配置；
- 不修改或提交 `web/dist` 构建产物，除非项目既有发布流程明确要求。

## 3. 核心概念

### 3.1 凭证 Credential

代表一组可用于认证的密文或浏览器状态，例如 Cookie、Bearer Token、API Key、Header 集合、Playwright `storageState`。凭证是可刷新、可版本化、可加锁的资源。

### 3.2 认证配置 Auth Config

描述如何登录、刷新和识别凭证，包括登录 URL、刷新 URL、请求模板、响应字段映射、浏览器登录地址、OTP 类型和目标域名。认证配置属于凭证，不属于业务配置。

### 3.3 业务绑定 Credential Binding

把凭证绑定到具体业务场景，并声明如何投影和使用。业务配置只保存 `credentialBindingId`，不保存凭证明文。

### 3.4 投影 Projection

将统一存储的凭证转为目标客户端所需的形式：

- HTTP Header：生成 `Authorization`、`X-API-Key` 或其他 Header；
- HTTP Cookie：生成请求 Cookie；
- Playwright storage：生成符合 Playwright `storageState` 的 JSON。

### 3.5 租约 Lease

用于控制刷新或使用过程中的并发。租约必须带有持有者、过期时间、用途和凭证版本，避免并发刷新以及单点登录系统中的相互失效。

## 4. 数据模型

建议使用以下独立表。具体字段名可以按项目 ORM 规范调整，但语义和约束不能改变。

### 4.1 `auth_credential`

| 字段 | 说明 |
| --- | --- |
| `id` | 凭证 ID；对外 BIGINT 必须序列化为字符串 |
| `name` | 凭证名称 |
| `credential_type` | `browser_storage`、`http_cookie`、`http_token`、`http_api_key`、`http_header` |
| `auth_mode` | `manual`、`http_login`、`http_refresh`、`browser_login`、`browser_refresh` |
| `secret_ciphertext` | 加密后的凭证内容，禁止明文返回 |
| `secret_version` | 凭证内容版本，用于乐观锁和回写冲突判断 |
| `status` | 可用、失效、刷新中、错误等状态 |
| `auto_refresh_enabled` | 是否参加自动刷新 |
| `refresh_interval_seconds` | 刷新检查或刷新间隔 |
| `expires_at` | 可推断的过期时间，可为空 |
| `last_checked_at` | 最近一次可用性检查时间 |
| `last_refreshed_at` | 最近一次成功刷新时间 |
| `last_refresh_error` | 最近一次刷新错误，禁止写入完整密文 |
| `created_at`、`updated_at` | 审计时间 |

### 4.2 `auth_credential_auth_config`

| 字段 | 说明 |
| --- | --- |
| `credential_id` | 关联凭证 |
| `login_url` | HTTP 登录地址 |
| `refresh_url` | HTTP 刷新地址 |
| `request_template` | 登录或刷新请求模板，敏感字段必须加密或引用安全存储 |
| `response_mapping` | Token、Cookie、过期时间等字段映射 |
| `browser_login_url` | 浏览器登录地址 |
| `otp_type` | `none`、`totp`、`sms`、`email`、`manual_confirmation` |
| `target_origins` | 允许投影的目标域名或 Origin 范围 |
| `refresh_options` | 站点特定的刷新判断和请求选项 |

系统不需要推断认证系统的归属。用户可以将 HTTP 和 Web 绑定到同一个凭证，也可以配置两个完全独立的凭证。

### 4.3 `auth_credential_binding`

| 字段 | 说明 |
| --- | --- |
| `id` | 绑定 ID；业务配置实际引用此 ID |
| `credential_id` | 关联凭证 |
| `business_type` | `web_case`、`ticket_log_pull`、`ticket_remote_sync` |
| `projection_type` | `playwright_storage`、`http_cookie`、`http_header` |
| `target_url` | 业务实际访问地址 |
| `origin` | 投影目标 Origin |
| `domain_scope` | Cookie 或 Header 允许作用的域名范围 |
| `concurrency_policy` | `shared_read`、`exclusive_refresh`、`exclusive_use` |
| `writeback_enabled` | 是否允许该绑定回写运行结果 |
| `enabled` | 是否可被业务选择 |
| `remark` | 配置说明 |

同一凭证可以有多个业务绑定，例如同一登录状态分别绑定 Web 执行和日志拉取；但绑定仍然可以声明不同的投影和并发策略。

### 4.4 `auth_credential_operation_log`

记录创建、读取、解析、刷新、写回、冲突、租约、失败等操作。日志必须记录凭证 ID、绑定 ID、业务类型、操作类型、结果、错误摘要、版本和操作者，不得记录 Cookie、Token、密码、OTP 或完整请求体。

### 4.5 `auth_credential_lease`

建议字段包括凭证 ID、绑定 ID、用途、持有者、租约 Token、开始时间、过期时间、凭证版本和状态。租约获取必须是原子操作，释放时校验持有者和租约 Token。

## 5. 枚举和配置约束

### 5.1 凭证类型

- `browser_storage`：Playwright `storageState`，包含 cookies 和 origins/localStorage 等状态；
- `http_cookie`：Cookie 集合；
- `http_token`：Bearer、Access Token、Refresh Token 等 Token；
- `http_api_key`：API Key；
- `http_header`：一个或多个固定或动态 HTTP Header。

### 5.2 认证方式

- `manual`：用户手工录入或手工保存，不自动登录；
- `http_login`：调用登录 HTTP 接口获取新凭证；
- `http_refresh`：使用 Refresh Token 或刷新接口更新凭证；
- `browser_login`：使用浏览器完成登录；
- `browser_refresh`：使用浏览器保持或恢复登录状态。

### 5.3 并发策略

- `shared_read`：允许多个业务同时读取，不允许并发修改；适用于 API Key 和稳定 Token；
- `exclusive_refresh`：读取可以共享，但刷新时同一凭证只能有一个执行者；
- `exclusive_use`：凭证使用期间只允许一个持有者，适用于新登录会使其他会话失效的单点登录系统。

如果站点限制“同账号单点登录”，或者刷新会使旧 Cookie 立即失效，必须使用 `exclusive_use`，并将业务执行纳入租约生命周期。后来的任务不能直接拿到同一凭证；应等待、失败或使用另一凭证，不能静默覆盖。

## 6. 凭证存储和投影规则

### 6.1 存储规则

1. 凭证明文只在创建、刷新、解析和必要的回写路径短暂存在内存中。
2. 数据库存储必须使用加密密文；查询列表、详情、下拉选项和普通日志均不得返回明文。
3. 更新操作必须使用版本号或更新时间做乐观锁校验。
4. 错误日志只能记录目标地址、状态码、字段名和脱敏摘要，不得记录认证值。
5. 任何业务配置都不能重复存储 Cookie、Authorization、Token 或密码。

### 6.2 HTTP Header 投影

`http_token` 或 `http_header` 凭证可以投影成 Header。例如：

```json
{
  "headerName": "Authorization",
  "valuePrefix": "Bearer ",
  "valueField": "accessToken"
}
```

API Key 示例：

```json
{
  "headerName": "X-API-Key",
  "headerValue": "真实密钥"
}
```

API Key 属于 `manual` 认证，默认 `autoRefreshEnabled=false`。只有用户明确配置刷新接口，才允许把它改造成可刷新凭证。

### 6.3 HTTP Cookie 投影

`http_cookie`、`browser_storage` 或包含 Cookie 的 Token 凭证可以投影为 HTTP Cookie。投影时必须根据绑定的 `target_url`、`origin` 和 `domain_scope` 过滤 Cookie，不能把一个域的 Cookie 发到不匹配的域名。

### 6.4 Playwright storage 投影

`browser_storage` 凭证只能通过 `playwright_storage` 绑定用于 Web 执行或录制恢复。投影结果必须保持 Playwright `storageState` 结构，至少正确处理 `cookies` 和 `origins`，不要把它粗暴转换成普通 Cookie 字符串而丢失 LocalStorage。

### 6.5 Session 转 Cookie

Session 不是业务侧需要理解的特殊类型。请求 HTTP 接口时，业务选择一个允许 `http_cookie` 或 `http_header` 投影的 `credentialBindingId`，凭证模块自动解析 Session 内的 Cookie/Header 并注入请求。业务层只传绑定 ID，不自行读取或拼接 Session。

## 7. 刷新和定时任务

定时任务是凭证管理模块的通用维护任务，不按业务分别实现一套刷新逻辑。任务扫描启用的凭证，按以下顺序判断：

1. 凭证是否启用、是否允许自动刷新；未启用或手工模式直接跳过；
2. 是否已经到达 `refresh_interval_seconds`，或已接近/超过 `expires_at`；未到时间跳过；
3. 凭证是否处于刷新中、是否已有有效 `exclusive_refresh` 租约；已有其他执行者则跳过；
4. 认证方式是否支持 HTTP 刷新或浏览器刷新；不支持则记录不可刷新原因，不强行执行；
5. 获取租约后重新读取最新版本和时间，避免扫描期间其他任务已经完成刷新；
6. 执行刷新并解析结果；
7. 将新凭证与旧版本比较。内容、有效期或投影结果没有变化时只更新检查时间和结果，不制造无意义的新版本；发生变化时写入新密文、版本、有效期和刷新时间；
8. 成功后写入操作日志并释放租约；失败时保留旧凭证、记录错误并释放租约。

刷新判断必须支持两种场景：

- “固定时间刷新”：例如每 30 分钟检查一次；
- “有效期刷新”：例如 Token 剩余 5 分钟时刷新。

不支持自动刷新的凭证仍可被业务读取。读取时若发现凭证已失效，应返回明确的凭证不可用错误，不自动猜测登录流程。

## 8. HTTP 登录和刷新

每个凭证的认证配置由用户决定：

- 是否支持 HTTP 登录；
- 是否支持 Refresh Token；
- 登录和刷新 URL；
- 请求模板和响应字段映射；
- 哪些字段是 Token、Cookie、过期时间或版本标识；
- 是否因新登录使旧 Cookie 失效；
- 是否限制同账号并发任务；
- OTP 类型和所需人工步骤；
- Authorization 是否来自 LocalStorage 或其他浏览器存储。

系统不假设所有外部平台有统一协议。HTTP 刷新器必须基于配置驱动，不能把某个平台的字段名硬编码成全局规则。

### OTP

- `totp`：如果配置了安全的 TOTP 密钥，可以由服务端按明确授权自动生成；
- `sms`：通常需要人工输入或外部短信服务，不应在系统内猜测；
- `email`：通常需要人工输入或邮件服务集成；
- `manual_confirmation`：暂停等待人工确认；
- `none`：登录不需要 OTP。

浏览器登录遇到 OTP 时必须保留明确的等待、失败和超时状态，不能把未完成登录的浏览器状态保存成“可用凭证”。

## 9. 乐观锁、租约和回写

### 9.1 乐观锁

所有刷新和回写请求都携带读取时的 `secret_version`。写入条件必须包含当前版本仍等于读取版本：

```text
UPDATE auth_credential
SET secret_ciphertext = new_value,
    secret_version = old_version + 1
WHERE id = credential_id
  AND secret_version = old_version
```

影响行数为 0 表示版本冲突。冲突时不得覆盖新版本，应重新读取并判断是否已经满足业务需求。

### 9.2 租约

- 刷新使用 `exclusive_refresh` 租约；
- 单点登录或会导致其他会话失效的凭证使用 `exclusive_use` 租约；
- 租约必须有超时，防止进程崩溃后永久占用；
- 长任务需要续租，续租必须校验租约 Token；
- 释放租约必须幂等；
- 租约冲突必须记录操作日志。

### 9.3 Web 客户端回写

普通 Web 执行默认只读取统一凭证，不回写。只有同时满足以下条件时才允许回写：

1. Web 执行或绑定明确开启 `writeback_enabled`；
2. 客户端本地浏览器状态缓存已启用；
3. 执行者持有正确的绑定和凭证版本；
4. 回写内容通过安全解析和域名过滤；
5. 乐观锁校验通过。

回写冲突时保留服务端较新版本，并把冲突结果返回给调用方和写入操作日志。

## 10. 业务接入

### 10.1 通用约定

业务配置只保存：

```json
{
  "credentialBindingId": "12"
}
```

业务执行前调用凭证模块的解析服务，获得短生命周期的投影结果。业务不得直接查询 `secret_ciphertext`，不得直接拼装认证 Header/Cookie。

### 10.2 远端工单同步

远端同步功能保留。新配置使用绑定引用：

```json
{
  "remoteSync": {
    "credentialBindingId": "12",
    "origin": "https://tickets.example.com"
  }
}
```

API Key 配置建议：

```json
{
  "credentialType": "http_api_key",
  "authMode": "manual",
  "autoRefreshEnabled": false,
  "businessType": "ticket_remote_sync",
  "projectionType": "http_header",
  "headerName": "X-API-Key"
}
```

旧的内联 `headers.cookie` 和 `headers.authorization` 不再读取。远端同步没有被删除，用户只需要把 API Key 重新配置到凭证管理模块并将绑定 ID 写入同步配置。

### 10.3 工单日志拉取

日志拉取配置示例：

```json
{
  "environments": {
    "prod": {
      "insertUrl": "https://logs.example.com/insert",
      "pageUrl": "https://logs.example.com/page",
      "credentialBindingId": "12",
      "origin": "https://logs.example.com",
      "vendors": []
    }
  }
}
```

请求时由绑定解析 HTTP Header 或 Cookie。旧的 `headers.cookie`、`headers.authorization` 不再读取。

日志拉取外部环境的地址、Origin、商家等配置不在统一凭证页面维护，继续通过系统参数 `ticket.logPull.external` 配置；环境配置只引用 `credentialBindingId`。

### 10.4 Web 执行

Web 执行请求使用 `credentialBindingId`，并且绑定必须满足：

- `businessType=web_case`；
- `projectionType=playwright_storage`；
- 凭证类型通常为 `browser_storage`；
- 目标 Origin 和域名范围匹配当前用例。

旧的 `browserSessionId`、`runtimeProfileId`、Browser Session 和 Runtime Profile 选择入口都应移除。普通执行只从统一凭证获取 `storageState`，本地缓存和回写由明确的配置开关控制。

### 10.5 Web 录制和自动创建凭证

录制时可以没有可用凭证。必须保留以下流程：

1. 开始录制时允许不选择已有凭证；
2. 用户在录制浏览器中手工完成登录；
3. 停止录制时提供“停止后保存凭证”选项；
4. 用户填写凭证名称、目标 Origin 和必要的并发/回写策略；
5. Agent 上报最终 `storageState`；
6. 服务端创建 `browser_storage` 凭证；
7. 服务端同时创建 `web_case` + `playwright_storage` 绑定；
8. 返回新的绑定 ID，后续 Web 执行选择这个绑定。

未完成登录、缺少有效 Cookie/LocalStorage 或 Origin 不匹配时，不得创建“可用”凭证。创建凭证接口必须走统一凭证服务，不能在 Web 录制模块中另存一套状态。

## 11. 对现有配置和代码的影响

以下内容必须删除或停止使用，不做兼容读取：

- `hrm.web.browser.session.*` 配置及相关服务；
- `hrm.web.runtime.profile.*` 配置及相关服务；
- `browserSessionId`；
- `runtimeProfileId`；
- `cookieRules`；
- Web Session、Runtime Profile 的前端入口、API、弹窗和状态管理；
- 旧的内联 `headers.cookie`；
- 旧的内联 `headers.authorization`；
- 任何绕过凭证管理直接读写浏览器状态或认证 Header 的逻辑。

保留并改造：

- 远端工单同步功能；
- 工单日志拉取功能；
- Web 录制功能；
- 客户端本地浏览器状态缓存；
- 录制停止后由最终 `storageState` 创建凭证的流程。

### 发布后用户需要重新配置

1. 在凭证管理中重新创建所有需要使用的 API Key、Cookie、Token、Header 和浏览器状态凭证；
2. 为每个凭证配置认证方式、刷新能力、过期判断、目标域名和 OTP 类型；
3. 创建对应的业务绑定，并选择投影类型和并发策略；
4. 将远端工单同步配置改为 `remoteSync.credentialBindingId`；
5. 将各环境工单日志拉取配置改为 `credentialBindingId` 和 `origin`；
6. 将 Web 用例绑定到 `web_case` + `playwright_storage` 绑定；
7. 如需客户端状态回写，显式开启本地缓存和回写开关；
8. 对限制单点登录的账号配置 `exclusive_use`，不能和其他任务共享。

## 12. 后端接口建议

接口前缀：`/system/credentials`。

至少提供：

- 凭证分页查询；
- 新增、更新、删除凭证；
- 手工刷新凭证；
- 查询、新增、更新、删除绑定；
- 按业务类型查询绑定下拉项；
- 解析指定绑定的投影；
- Web 录制状态创建凭证；
- 查询操作日志和当前租约状态（敏感信息脱敏）。

已有业务接口建议：

- Web 执行请求增加 `credentialBindingId`；
- `POST /hrm/web-case/recording/{recording_id}/credential`。

接口契约要求：

- 对外 Pydantic/Schema 契约与 ORM 解耦；
- BIGINT ID 对外统一序列化为字符串；
- 密文、密码、Cookie、Token、OTP 永不出现在响应；
- 错误响应区分未配置、无权限、租约冲突、版本冲突、凭证失效和刷新失败；
- 写操作必须有审计日志。

## 13. 实施顺序

1. 创建数据库表、索引、唯一约束和状态枚举；
2. 实现加密工具、实体、DAO、Schema/VO 和基础服务；
3. 实现绑定解析和三类投影；
4. 实现租约、乐观锁和操作日志；
5. 实现 HTTP 登录/刷新配置驱动能力；
6. 接入通用定时刷新任务，并确保失败不覆盖旧版本；
7. 接入工单日志拉取；
8. 接入远端工单同步 API Key/Header；
9. 接入 Web 执行的 Playwright `storageState`；
10. 保留并改造 Web 录制后的自动建凭证流程；
11. 完全移除 Browser Session、Runtime Profile 旧逻辑和前端入口；
12. 删除旧配置读取和旧内联认证字段；
13. 更新前端、用户文档和 Wiki；
14. 完整执行后端测试、前端生产构建和关键流程验收。

每一步完成后再进入下一步。构建或测试必须等待进程明确退出，并记录退出码；不能在进程仍运行时报告完成。

## 14. 验收测试清单

### 数据和安全

- [ ] 凭证明文只在加密存储中保存；
- [ ] 列表、详情、下拉项和错误日志均不泄露密文；
- [ ] BIGINT ID 对外是字符串；
- [ ] 删除凭证时正确处理绑定和运行中租约；
- [ ] 业务配置中不存在 Cookie、Authorization、Token 等内联认证值。

### 投影

- [ ] API Key 可以投影成指定 Header；
- [ ] Token 可以按配置投影成 Authorization；
- [ ] Session/浏览器状态可以按域名投影成 Cookie；
- [ ] Playwright `storageState` 保留 cookies 和 origins/localStorage；
- [ ] 不匹配的 Origin 或域名不会收到 Cookie。

### 刷新

- [ ] 未到刷新时间的凭证会被跳过；
- [ ] 已过期或接近过期的凭证会按配置刷新；
- [ ] `autoRefreshEnabled=false` 的 API Key 不会被定时任务刷新；
- [ ] 同一凭证并发刷新只有一个执行者；
- [ ] 刷新失败保留旧版本；
- [ ] 刷新结果未变化时不制造新版本；
- [ ] 版本冲突不会覆盖更新后的凭证；
- [ ] 租约超时后可以恢复执行。

### 业务

- [ ] 远端同步仍可使用 API Key；
- [ ] 日志拉取只通过绑定解析认证信息；
- [ ] Web 执行只接受 `web_case` + `playwright_storage` 绑定；
- [ ] 普通 Web 执行默认不回写；
- [ ] 开启本地缓存和回写开关后可以按版本安全回写；
- [ ] 单点登录凭证的 `exclusive_use` 可以阻止并发使用；
- [ ] 录制时无已有凭证也可以手工登录并创建新凭证和绑定；
- [ ] 未完成登录的录制状态不能创建可用凭证；
- [ ] 旧 Browser Session、Runtime Profile 入口和 API 不再可用。

### 工程质量

- [ ] Controller、Service、DAO 分层清晰；
- [ ] 异步接口不直接执行阻塞 HTTP、浏览器或数据库操作；
- [ ] Loguru 日志使用 f-string，且敏感内容脱敏；
- [ ] 关键公共方法有中文方法注释；
- [ ] 新增或修改代码有对应单元测试/接口测试；
- [ ] Wiki 和用户文档已同步；
- [ ] 前端生产构建完成并有明确退出码；
- [ ] 不提交 `web/dist` 非必要构建产物。

## 15. 当前实施记录

按此前实施记录，项目已经具备或曾经加入以下内容，后续模型应先检查实际工作区再继续，不要重复创建：

- `server/sql/20260805_credential_management.sql`；
- `server/modules/credential/` 独立后端模块；
- `/system/credentials` 凭证和绑定管理接口；
- 工单日志拉取继续使用系统参数 `ticket.logPull.external`，统一凭证页面不提供其可视化编辑；
- 远端同步通过 `remoteSync.credentialBindingId` 使用凭证；
- Web 执行的 `credentialBindingId` 和 Playwright storage 投影；
- 录制后创建凭证接口 `POST /hrm/web-case/recording/{recording_id}/credential`；
- 用户文档和 Wiki 中的凭证管理说明。
- 2026-08-06 增补 HTTP 登录/刷新配置：登录与刷新请求分开配置，支持用户名、密码、TOTP、请求参数、JSON/表单请求体，支持从 JSON、响应头和 `Set-Cookie` 提取新凭证；HTTP 刷新自动携带当前 Cookie/Header，手工录入且无账号密码的凭证也可自动续期。`browser_refresh` 仍需 Agent/浏览器执行，不参加服务端定时任务。

此前前端生产构建曾明确成功，结果为 `2889 modules transformed`、退出码 `0`，仅有既有的 `/config.js` 非 module、`eval` 和 chunk 体积警告。后续任何清理旧逻辑后的构建都必须重新执行并等待明确结果，不能仅引用此前结果。

## 16. 后续模型执行规则

后续模型接手本项目时必须：

1. 先阅读本文件，再检查当前 Git 状态和实际代码；
2. 优先使用 `codebase-memory` 知识图谱定位定义、调用者和影响范围；
3. 不恢复已明确删除的旧兼容逻辑；
4. 不迁移旧凭证数据，不擅自保留旧字段兼容读取；
5. 任何新业务认证都通过 `credentialBindingId` 接入；
6. 不在业务模块复制刷新、加密、投影或回写逻辑；
7. 先完成一组完整改动，再执行测试和构建；
8. 对长时间构建、测试或服务进程持续等待到明确退出或明确失败；
9. 修改文件前在 commentary 中说明范围，完成后说明实际改动和验证结果；
10. 若发现本文件与用户最新明确要求冲突，以用户最新要求为准，并同步更新本文件。
