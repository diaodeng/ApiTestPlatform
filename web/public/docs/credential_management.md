# 统一凭证管理

统一凭证管理把 Cookie、浏览器 Session、Authorization、API Key 等认证信息从业务配置中移出，集中加密保存、刷新和审计。业务配置仅保存“凭证绑定 ID”。

入口：系统管理 → 统一凭证管理。先创建凭证，再创建业务绑定，最后把绑定 ID 填入对应业务配置。

统一凭证管理页面只维护凭证和业务绑定，不提供日志拉取外部环境的编辑入口。日志拉取的环境地址、Origin、商家等配置继续通过系统参数维护，参数键为 `ticket.logPull.external`；其中每个环境只填写 `credentialBindingId` 引用统一凭证，不填写 Cookie、Authorization 或 API Key。

## 远端工单同步

远端同步配置的 `credentialBindingId` 必填。请创建 `http_api_key` 或 `http_header` 凭证，敏感字段示例为 `{"headerName":"X-API-Key","headerValue":"你的密钥"}`，认证方式选“手工”，关闭自动刷新；再创建 `ticket_remote_sync`、`http_header` 绑定。

`origin` 是非敏感请求头，可仍在远端同步配置中填写。旧 `headers.cookie` 和 `headers.authorization` 不再生效。

## 工单日志拉取

每个日志拉取环境在系统参数 `ticket.logPull.external` 中配置 `credentialBindingId`。如果日志接口要求 Cookie，可创建 `browser_storage` 凭证，并使用 `http_cookie` 投影绑定；系统只会把匹配目标地址域名、路径和 HTTPS 规则的 Cookie 转换为请求头。系统参数页面入口为：系统管理 → 参数设置。

## 凭证内容和登录参数

新增凭证弹窗中的“凭证内容”是会被加密保存的敏感快照：Cookie 填 `SESSION=...`，Header/API Key 填 Header 名称和值，Token 填 Token 和值前缀，浏览器凭证填 Playwright `storageState`。编辑已有凭证时敏感值不会回显，留空表示保留原值。

选择“HTTP 登录”时可配置用户名、密码、OTP 类型和登录接口。请求 Header、查询参数、JSON 请求体、表单请求体分别填写 JSON 对象；请求体可使用 `${secret.username}`、`${secret.password}`、`${secret.otp}` 引用加密字段。TOTP 需要填写 TOTP 密钥，短信、邮箱和人工确认 OTP 不能由定时任务自动完成。

选择“HTTP 刷新”时可配置独立的刷新接口和参数。系统会自动携带当前凭证的 Cookie/Header，因此手工录入、没有账号密码的 Cookie 或 Token 也可以通过刷新接口更新。响应提取规则支持 `json:data.accessToken`、`header:X-Auth-Token`、`cookie:SESSION` 和 `cookies`；未填写 Cookie 映射时，响应头中的 `Set-Cookie` 也会自动合并到当前快照。

## 刷新与并发

静态 API Key 选择 `manual`，不会参加刷新任务。HTTP 登录/刷新凭证可开启自动刷新并设定间隔；`manual` 不能开启自动刷新，需要“手工录入初始值 + 自动续期”时请选择 `HTTP 刷新`。刷新失败会保留旧凭证；人工保存或刷新写回使用版本号，发生冲突时不会覆盖新版本。

会使同账号会话失效的系统应选择 `exclusive_refresh` 或 `exclusive_use`，刷新和独占业务执行会使用短期租约阻止并发。

浏览器凭证用于普通 Web 用例时只读，不会因测试过程自动回写。录制、回放和执行弹窗只显示 `web_case` + `playwright_storage` 的凭证绑定；旧 Browser Session 和 Runtime Profile 入口已移除。

如需回写浏览器状态，必须同时在 Web 绑定中开启“允许回写”、启用客户端本地浏览器状态缓存，并携带读取时的凭证版本；普通执行默认不会调用回写接口。

录制完成后，如需保存手工登录结果，请开启“停止后保存凭证”并填写名称。系统会在 Agent 上报最终浏览器状态后新建浏览器凭证和 Web 用例绑定；这是一项显式保存操作，不会覆盖已有凭证。

前端加载业务绑定选项时使用查询参数 `businessType`，可选值为 `web_case`、`ticket_log_pull`、`ticket_remote_sync`。
