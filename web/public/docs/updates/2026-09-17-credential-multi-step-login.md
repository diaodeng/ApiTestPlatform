# 统一凭证支持多步登录链（两步及以上自动认证）

- 背景：部分系统（如 rta-os ERP）登录是多步骤流程——账号密码登录成功后服务端返回一次性 `ticket`，需再用 TOTP 验证码调用 `/doOtp` 换回会话 Cookie。原"HTTP 登录"只有单次请求模板，无法表达"第二步参数来自第一步响应"，也无法以 multipart 提交验证码。
- 后端新增**多步登录链**能力（`authConfig.loginSteps`）：
  - 按顺序执行多个 HTTP 步骤，整条链共用一个会话（第一步响应的 `Set-Cookie` 自动带入后续请求，如 WAF 的 `acw_tc`）；
  - 步骤请求体支持 `none`/`form`/`json`/`multipart`（multipart boundary 由服务端自动生成）；
  - 每步独立成功断言；`persistOutputs=false` 的输出是临时步骤变量（如一次性 ticket，经 `${step.N.变量}` 引用，不写入凭证密文），`persistOutputs=true` 的输出按响应提取规则写回凭证；
  - 提取来源新增一次加工语法：`json:路径|url_query:参数名`、`json:路径|regex:正则`；
  - TOTP（`otp_type=totp`）在每个步骤执行前按 RFC 6238 重新生成，支持账密 + TOTP 全自动登录；任意一步失败整链终止并保留旧凭证快照；
  - `http_refresh` 刷新失败后的兜底登录同样支持走多步链；`loginSteps` 为空时行为与原单步登录完全一致，存量凭证零影响。
- 新增接口 `POST /system/credentials/{id}/test-login-flow`：真实执行多步登录链并返回逐步明细（状态码、耗时、输出变量、写回字段），不写回凭证，用于保存前验证配置与排查 TOTP 时间偏差。
- 数据库变更：需执行 `server/sql/20260917_credential_login_steps.sql`，为 `auth_credential_auth_config` 新增 `login_steps` JSON 列（NULL 兼容旧数据）。
- 重构：把响应来源读取、断言校验、Cookie 写回、TOTP 生成、请求日志脱敏等公共能力从刷新服务下沉到 `modules/credential/util/credential_http_util.py`，单步刷新与多步链共用，无行为变化。
- 已知边界：短信/邮箱/人工 OTP 无法定时自动完成（沿用既有校验）；ticket 一次性，任何一步失败整链重跑；步骤数上限 5。
- 本期为后端能力，前端步骤可视化编辑器为下一期计划；当前可通过凭证编辑接口提交 `authConfig.loginSteps` 配置。配置方法与完整示例见用户说明：[统一凭证管理](../credential_management.md)。
