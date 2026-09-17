# 统一凭证管理

统一凭证管理把 Cookie、浏览器 Session、Authorization、API Key 等认证信息从业务配置中移出，集中加密保存、刷新和审计。业务配置仅保存"凭证绑定 ID"。

入口：系统管理 → 统一凭证管理。先创建凭证，再创建业务绑定，最后把绑定 ID 填入对应业务配置。

统一凭证管理页面只维护凭证和业务绑定，不提供日志拉取外部环境的编辑入口。日志拉取的环境地址、Origin、商家等配置继续通过系统参数维护，参数键为 `ticket.logPull.external`；其中每个环境只填写 `credentialBindingId` 引用统一凭证，不填写 Cookie、Authorization 或 API Key。

> 业务绑定新增和编辑是两条独立操作；点击“新增绑定”时会清空上一次编辑留下的绑定主键，因此同一业务、同一投影类型也可以继续新增多条绑定记录。
## 大数据查询

大数据查询（Unidata）业务场景用于托管外部大数据查询服务的认证信息，目前仅支持「纳入统一凭证、创建 HTTP Header 投影绑定」，暂未接通到具体的查询执行链路。

- **凭证类型**：`http_api_key` 或 `http_header`，认证方式选「手工」，关闭自动刷新。
- **敏感字段示例**：`{"headerName":"Authorization","headerValue":"Bearer unid***TnZw"}`（`Bearer` 后保留一个空格）。
- **业务绑定**：业务场景选「大数据查询」（`external_data_query`），投影方式选 `http_header`。
- `workbenchCode` 属非敏感请求参数，不在敏感快照中维护；查询执行时在请求侧拼接。目标域白名单建议配置到对应环境域名（如 UAT `uatopen-d.rta-os.com`），Prod 环境单独建绑定并配生产域名，避免凭证被投影到非预期站点。

## 远端工单同步

远端同步配置的 `credentialBindingId` 必填。请创建 `http_api_key` 或 `http_header` 凭证，敏感字段示例为 `{"headerName":"X-API-Key","headerValue":"你的密钥"}`，认证方式选"手工"，关闭自动刷新；再创建 `ticket_remote_sync`、`http_header` 绑定。

`origin` 是非敏感请求头，可仍在远端同步配置中填写。旧 `headers.cookie` 和 `headers.authorization` 不再生效。

## 工单日志拉取

每个日志拉取环境在系统参数 `ticket.logPull.external` 中配置 `credentialBindingId`。如果日志接口要求 Cookie，可创建 `browser_storage` 凭证，并使用 `http_cookie` 投影绑定；系统只会把匹配目标地址域名、路径和 HTTPS 规则的 Cookie 转换为请求头。系统参数页面入口为：系统管理 → 参数设置。

历史日志拉取记录重新拉取时，不再自动回退到第一个环境；如果原记录没有保存环境信息，会直接报错“当前记录缺少环境信息，无法重新拉取”。如果环境存在但绑定的统一凭证已失效、解绑或不匹配目标地址，系统会直接返回“日志拉取外部接口凭证不可用：...”的明确错误，便于排查旧记录无法重拉的原因。

## 凭证内容和登录参数

新增凭证弹窗中的"凭证内容"是会被加密保存的敏感快照。**一个凭证只能选择一种类型，对应一组认证信息。** 填写方式：

- **HTTP Cookie**：完整的 Cookie 字符串，多个键值对用分号+空格分隔，例如 `SESSION=abc123; tenant=prod; locale=zh-CN`。系统会自动解析并在请求时携带。
- **HTTP Token**：分为三个字段——Header 名称（如 `Authorization`）、值前缀（如 `Bearer `，注意末尾空格）、Token 值（不含前缀的令牌值）。系统自动拼接为 `{值前缀}{Token}` 放入请求头。
- **API Key / HTTP Header**：填写 Header 名称（如 `X-API-Key`）和 Header 值（密钥内容）。一个凭证只对应一组 Header 键值对。
- **浏览器状态**：填写 Playwright `storageState` JSON，如 `{"cookies":[],"origins":[]}`。

编辑已有凭证时会读取并回填已保存的敏感值，输入框默认以掩码显示；点击输入框右侧眼睛图标可临时查看明文。**把已保存的字段清空后保存，会从凭证中删除该字段**（例如清空账号和密码后保存，凭证中就不再保存登录账号）。切换凭证类型保存后，旧类型的主凭证字段会被清除，附加 Header、附加 Cookie、账号和密码等共享字段保留。

### 更新方式

| 方式 | 适用场景 | 自动刷新 |
|---|---|---|
| 手工录入 | 长期有效的 API Key / 静态 Token | 不支持 |
| HTTP 登录 | 需要账号密码登录获取凭证 | 支持（TOTP 可自动） |
| HTTP 刷新 | 用现有 Cookie/Header 调刷新接口续期；可配置兜底登录接口，刷新失败后自动登录并重试 | 支持 |
| 浏览器人工登录 | 人工在浏览器中登录 | 不支持 |
| 浏览器刷新 | 浏览器自动刷新状态 | 视实现而定 |

手工录入初始值后想自动续期，请选择"HTTP 刷新"并按需配置刷新接口和兜底登录接口。

### 附加认证信息和其他敏感字段

主凭证始终显示在“凭证内容”区域；“附加认证信息（可选）”折叠区只在需要额外认证材料时展开。

- **附加 Header**：以键值对方式填写，例如 `X-CSRF-Token: abc`、`X-Tenant: prod`。请求登录、刷新和业务使用凭证时都会携带。
- **附加 Cookie**：以键值对方式填写，例如 `CSRF-TOKEN: abc`。会与主 Cookie、浏览器状态中的 Cookie 合并，同名 Cookie 以后写入者覆盖前者。
- **Cookie 来源约束**：主 Header 名称为 `Cookie` 时，必须在主 Header 值中维护完整 Cookie 字符串，不能再新增或编辑结构化附加 Cookie；响应提取也不能写入 `cookies` 或 `cookies.名称`。请改用 `header.cookie` 或 `header.cookie.名称` 更新主 Cookie Header。若历史凭证同时保存了结构化附加 Cookie，页面会保留删除图标；逐项删除后保存，即可清理旧数据。
- **Header + Cookie 联合认证**：主 Header 为 `Authorization`、`X-API-Key`、`X-CSRF-Token` 等非 Cookie 认证时，仍可同时使用结构化附加 Cookie。这适用于 Token + 会话 Cookie、API Key + CSRF Cookie 等场景，刷新响应可以继续通过 `cookies` 或 `cookies.名称` 写回结构化 Cookie。
- **其他敏感字段 JSON**：仅存放没有专用表单项的敏感变量；不能再写 `headers` 或 `cookies`。这些值会加密保存，且可在请求模板中用 `${secret.字段名}` 引用。

其他敏感字段常见用途：
- 刷新令牌：`{"refreshToken": "xxx"}`
- 其他密钥：`{"clientSecret": "xxx"}`

### HTTP 登录参数

选择"HTTP 登录"时可配置用户名、密码、OTP 类型和登录接口。
- **用户名/密码**：目标系统的登录账号和密码，由用户自行填写。在请求模板中通过 `${secret.username}` 和 `${secret.password}` 引用。
- **OTP 类型**：TOTP 自动生成需要填写 TOTP 共享密钥（通常是一串 Base32 编码字符串），系统按 RFC 6238 自动计算 6 位验证码。短信、邮箱和人工确认 OTP 不能由定时任务自动完成。验证码通过 `${secret.otp}` 注入请求体。
- **默认请求模板**：新增凭证时，登录接口的 JSON 请求体会自动填入 `{"username":"${secret.username}","password":"${secret.password}"}` 默认模板；编辑已有凭证时不会自动改动请求体。如需找回默认模板，可点击登录接口"接口地址"旁的**恢复默认模板**按钮。不需要账号密码的凭证（例如仅靠 Cookie 刷新），清空请求体为 `{}` 保存即可，模板不会被再次填回。

### 请求模板占位符

登录/刷新请求的 JSON 请求体和表单请求体支持以下占位符，发送前系统会自动替换：

| 占位符 | 说明 |
|---|---|
| `${secret.username}` | 登录用户名 |
| `${secret.password}` | 登录密码 |
| `${secret.otp}` | OTP 验证码（自动生成或手工输入） |
| `${secret.token}` | 当前存储的 Token 值 |
| `${secret.cookie}` | 当前完整 Cookie 字符串；凭证类型为“HTTP Cookie”时读取 Cookie 字段，凭证类型为“API Key / HTTP Header”且 Header 名称为 `Cookie` 时读取 Header 值。 |
| `${secret.headerValue}` | **高级用法**。直接读取“API Key / HTTP Header”的主 Header 值；它描述存储字段，通常应优先使用 `${secret.cookie}`、`${secret.token}` 等业务语义变量。历史 `header_value` 字段也会兼容为该变量。 |
| `${secret.refreshToken}` | “其他敏感字段 JSON”中保存的刷新令牌；其他自定义字段可按 `${secret.字段名}` 使用。 |

页面会在 Header、查询参数、JSON 请求体和表单请求体旁提供“插入变量”按钮。光标位于 JSON 字符串外时，按钮会自动补全双引号；位于已有字符串内或选中原值时，会直接插入/替换变量，例如 `"${secret.cookie}"`。保存前会校验变量格式、未闭合占位符以及当前凭证是否存在被引用的字段；不支持 `${secret.header.cookie}` 这类嵌套路径。

### 响应提取规则

选择"HTTP 刷新"时，编辑页会同时展示刷新接口和兜底登录接口配置；系统会自动携带当前凭证的 Cookie/Header，因此手工录入、没有账号密码的 Cookie 或 Token 也可以通过刷新接口更新。若请求 Header 中需要显式填写 `cookie: ${secret.cookie}`，而凭证以“API Key / HTTP Header”类型保存且 Header 名称为 `Cookie`，系统会自动以该凭证的 Header 值替换占位符，无需重复把 Cookie 写入“其他敏感字段 JSON”。

刷新请求日志会脱敏所有请求 Header、Cookie 以及密码、Token 等敏感字段；日志只用于确认请求已组装，不能据此读取凭证明文。

响应提取规则的**凭证字段**（左）是明确的写入目标。只有配置了提取规则的字段会更新；响应中的 `Set-Cookie` 不再自动合并到凭证中。可以配置多条规则，分别更新 Header、Token 和结构化 Cookie。

| 凭证字段 | 适用场景 | 写入行为 |
|---|---|---|
| `token` | HTTP Token | 直接替换 Token 值。 |
| `header.cookie` | HTTP Header，且 Header 名称为 `Cookie` | 覆盖整个 Cookie Header。未包含的 Cookie 会丢失，属于高风险操作。 |
| `header.cookie.UYBFEWAEE` | HTTP Header，且 Header 名称为 `Cookie` | 仅替换 Cookie Header 中 `UYBFEWAEE` 的值；不存在时静默追加。Header 名称大小写不敏感。 |
| `cookies` | HTTP Cookie 或其他敏感字段中的结构化 Cookie | 用响应提取到的 Cookie 对象整体覆盖原 `cookies` 对象。 |
| `cookies.SESSION` | HTTP Cookie 或其他敏感字段中的结构化 Cookie | 仅更新 `cookies` 对象中的 `SESSION`，其他 Cookie 保留。 |
| `headerValue`、`headerName` | API Key / HTTP Header | 直接替换整个字段。 |

**来源**（右）是从响应中提取值的路径，格式为 `类型:路径`：
- `json:data.accessToken` — 从 JSON 响应体的 `data.accessToken` 路径提取
- `header:X-Auth-Token` — 从响应头提取
- `header:set-cookie` — 读取唯一一条 `Set-Cookie` 的原始值，不经过 Cookie 解析；适用于响应为 `Set-Cookie: new_value` 的非标准接口。
- `header:set-cookie[n]` — 从多条原始 `Set-Cookie` 中按序号选择一条，序号从 1 开始，例如 `header:set-cookie[1]`。不允许省略选择而把多条值拼接到一个字段中。
- `cookie:SESSION` — 从标准 `Set-Cookie: SESSION=new_value; Path=/` 中提取单个 Cookie 值
- `cookies` — 提取全部标准 `Set-Cookie` 为 Cookie 对象

例如刷新接口返回响应头 `Set-Cookie: new_value`，而现有 HTTP Header 凭证为 `Cookie: ...; UYBFEWAEE=old_value` 时，填写：凭证字段 `header.cookie.UYBFEWAEE`，来源 `header:set-cookie`。系统会仅替换 `UYBFEWAEE` 的值。

`cookies ← cookies` 是整组覆盖：响应中不存在的旧结构化 Cookie 会被删除；但响应中没有任何标准 `Set-Cookie` 时，不会把旧对象覆盖为空。需要保留其他 Cookie 时，请使用 `cookies.名称 ← cookie:名称` 等单项规则。提取结果只会写入配置的目标，其他未提取字段保留原值。

**Cookie 写回边界**：主 Header 名称为 `Cookie` 时，系统拒绝 `cookies` 和 `cookies.名称` 写入，避免主 Cookie Header 与结构化 Cookie 同时保存后页面无法再次提交。应使用 `header.cookie` 或 `header.cookie.名称`；主 Header 不是 `Cookie` 时，Header 认证与结构化 Cookie 可以正常共存。

### 成功断言

HTTP 登录或 HTTP 刷新的响应先通过 HTTP 状态码校验：只有 `2xx` 才会继续。随后执行“成功断言”中已配置的所有规则；全部通过后，系统才执行响应提取并写回凭证。断言和响应提取彼此独立：断言只判断接口是否成功，提取规则只决定哪些字段更新。

| 断言来源 | 示例 | 说明 |
|---|---|---|
| `status` | `status 等于 200` | HTTP 响应状态码。 |
| `json:code` | `json:code 等于 "0000"` | JSON 响应字段，支持点路径。 |
| `json:data.success` | `json:data.success 等于 true` | 嵌套 JSON 字段。 |
| `header:X-Result` | `header:X-Result 非空` | 响应头值。 |
| `cookie:SESSION` | `cookie:SESSION 存在` | 标准 `Set-Cookie` 中解析出的单个 Cookie。 |

支持的操作符为“等于、不等于、存在、非空、包含、属于”。除“存在、非空”外都需要填写期望值，期望值必须是合法 JSON：字符串写作 `"0000"`，布尔值写作 `true`，数字写作 `0`，多个允许值写作 `[200, 201]` 并配合“属于”。断言失败会保留旧凭证，并记录失败原因；不会执行响应提取或写回。

### 多步登录链（两步及以上认证）

有些系统的登录需要多个步骤，例如“账号密码登录 → 服务端返回一次性 ticket → 用 TOTP 验证码换回会话 Cookie”。单步登录模板表达不了“第二步的参数来自第一步响应”这类流程，此时可以为 HTTP 登录凭证配置**多步登录链**（`authConfig.loginSteps`，编辑接口按 camelCase 提交，目前通过接口或后续版本的可视化编辑器配置）。

配置后，定时刷新和手工刷新会按顺序执行整条链；`HTTP 刷新` 的兜底登录同样走多步链。**多步登录链为空时完全沿用原有单步登录模板**，已有凭证无需任何改动。

每个步骤包含以下配置：

| 字段 | 说明 |
|---|---|
| `name` | 步骤名称（可选），用于日志和测试结果展示。 |
| `url` / `method` | 步骤请求地址与方法，地址必须以 `http://` 或 `https://` 开头。 |
| `bodyType` | 请求体类型：`none` / `form`（表单）/ `json` / `multipart`。multipart 的 boundary 由系统自动生成，不需要也不应该手填 `Content-Type`。 |
| `headers` / `body` | 步骤请求头与请求体，支持下面的占位符。 |
| `successAssertions` | 本步骤独立成断言，规则与“成功断言”一致；任意一步失败整链终止。 |
| `outputs` | 本步骤从响应提取的变量。 |
| `persistOutputs` | `false`（默认）时输出为**临时步骤变量**，仅供后续步骤引用，认证结束即丢弃，不会写入凭证；`true` 时输出按“响应提取规则”写回凭证密文。 |

占位符与提取来源：

- `${secret.字段名}`：引用凭证敏感字段（与单步模板一致），TOTP 验证码用 `${secret.otp}`，系统在**每个步骤执行前**按当前时间窗口重新生成。
- `${step.N.变量名}`：引用第 N 步提取的临时变量（N 从 1 开始，只能引用更早的步骤）。
- 提取来源在原有 `json:路径`、`header:名称`、`cookie:名称`、`cookies` 基础上，支持追加一次加工：`json:result|url_query:ticket`（把来源值当作 URL 提取查询参数）、`json:result|regex:ticket=([0-9a-f-]+)`（按正则提取，有捕获组时取第 1 组）。

以“账密 + TOTP 两步登录”为例（对应 `rta-os` ERP 场景）：

```json
"loginSteps": [
  {
    "name": "账号密码登录",
    "url": "https://erp.example.com/doLogin",
    "method": "POST",
    "bodyType": "form",
    "body": {"account": "${secret.username}", "pwd": "${secret.password}", "remember": "1"},
    "successAssertions": [{"source": "json:code", "operator": "equals", "expected": "success"}],
    "outputs": {"ticket": "json:result|url_query:ticket"},
    "persistOutputs": false
  },
  {
    "name": "TOTP 验证",
    "url": "https://erp.example.com/doOtp",
    "method": "POST",
    "bodyType": "multipart",
    "body": {"ticket": "${step.1.ticket}", "google_code": "${secret.otp}"},
    "successAssertions": [{"source": "json:code", "operator": "equals", "expected": "success"}],
    "outputs": {"header.cookie.UYBFEWAEE": "cookie:UYBFEWAEE"},
    "persistOutputs": true
  }
]
```

**执行语义与注意事项**：

- 整条链共用一个会话：第一步响应的 `Set-Cookie`（如 WAF 下发的 `acw_tc`）会自动带入后续请求。
- 临时变量（如 ticket）是一次性的：任何一步失败整链作废重跑，不做单步重试；ticket 不会出现在凭证密文中。
- 链中至少要有一个 `persistOutputs=true` 的步骤提取到新凭证，否则视为登录失败并保留旧快照。
- 全部步骤成功后才按版本号写回凭证，与单步刷新一致；步骤数上限 5 个。
- 保存配置时会校验变量引用（只能引用更早步骤声明的输出）、来源语法和请求体类型（GET 不允许携带请求体）。
- 临时验证码场景（短信、邮箱、人工 OTP）无法由定时任务自动完成，仅 TOTP 支持全自动登录链。

**测试登录流程**：调用 `POST /system/credentials/{id}/test-login-flow`（权限同手工刷新，body 可传 `{"otpCode": "123456"}`，TOTP 场景可不传），系统会真实执行整条链并返回每一步的状态码、耗时、提取到的变量名和最终写回的凭证字段名；**无论成功与否都不会写回凭证密文**，可用于保存前验证配置和排查 TOTP 时间偏差等问题。

## 刷新与并发

静态 API Key 选择 `manual`，不会参加刷新任务。HTTP 登录/刷新凭证可开启自动刷新并设定间隔；`manual` 不能开启自动刷新，需要"手工录入初始值 + 自动续期"时请选择 `HTTP 刷新`。如果 HTTP 刷新同时配置了登录地址，服务端会先按刷新请求续期，刷新失败后自动执行登录，再用登录得到的新凭证重试刷新；人工保存或刷新写回使用版本号，发生冲突时不会覆盖新版本。

**自动刷新跳过原因**：定时刷新任务只处理"开启自动刷新"的凭证。未开启的凭证每次都会被跳过，并且对于 HTTP 登录/刷新模式但未开启自动刷新的凭证，系统**每天最多记录一条**"凭证未开启自动刷新"的操作审计日志提醒。凭证列表页提供"自动刷新"列，可以直接看到每个凭证是否开启、刷新间隔和最近一次刷新时间。

**到期时间**：编辑页"刷新与状态"区可设置凭证到期时间（可留空）。开启自动刷新后，到期前 5 分钟内即使未到刷新间隔也会触发一次刷新；未开启自动刷新的凭证到期后，业务在解析凭证时会直接收到"凭证已到期"的明确报错。

会使同账号会话失效的系统应选择 `exclusive_refresh` 或 `exclusive_use`，刷新和独占业务执行会使用短期租约阻止并发。

浏览器凭证用于普通 Web 用例时只读，不会因测试过程自动回写。录制、回放和执行弹窗只显示 `web_case` + `playwright_storage` 的凭证绑定；旧 Browser Session 和 Runtime Profile 入口已移除。

如需回写浏览器状态，必须同时在 Web 绑定中开启"允许回写"、启用客户端本地浏览器状态缓存，并携带读取时的凭证版本；普通执行默认不会调用回写接口。

录制完成后，如需保存手工登录结果，请开启"停止后保存凭证"并填写名称。系统会在 Agent 上报最终浏览器状态后新建浏览器凭证和 Web 用例绑定；这是一项显式保存操作，不会覆盖已有凭证。

前端加载业务绑定选项时使用查询参数 `businessType`，可选值为 `web_case`、`ticket_log_pull`、`ticket_remote_sync`。
