# 2026-08-09 凭证模板变量与 Cookie 写回边界

- 凭证编辑页的请求 Header、查询参数、JSON 请求体和表单请求体新增“插入变量”按钮，并在保存前校验凭证变量格式、是否闭合和当前凭证是否存在被引用字段。
- 保留 `${secret.cookie}` 的语义兼容：HTTP Header / API Key 凭证的主 Header 名称为 `Cookie` 时，变量自动读取主 Header 值。
- 新增 `${secret.headerValue}`，标记为高级用法；它直接读取主 Header 值，通常建议优先使用 `${secret.cookie}`、`${secret.token}` 等语义变量。
- 主 Header 名称为 `Cookie` 的凭证不再允许响应提取写入结构化 `cookies`；请使用 `header.cookie` 或 `header.cookie.名称`。主 Header 为 Authorization、API Key 等非 Cookie 时，Header 认证与结构化 Cookie 仍可同时使用。
- 刷新请求日志会脱敏全部请求 Header，避免 `${secret.headerValue}` 写入自定义 Header 后因 Header 名称未命中敏感词而泄露。
