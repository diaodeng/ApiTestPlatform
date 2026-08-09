# 2026-08-09 凭证刷新 Cookie 模板变量修复

- 修复“API Key / HTTP Header”类型凭证在 Header 名称为 `Cookie` 时，刷新请求模板中的 `${secret.cookie}` 未替换的问题。
- 现在该占位符会使用已加密保存的 Header 值生成刷新请求；无需将同一 Cookie 复制到其他敏感字段中。
- 刷新请求日志新增敏感字段脱敏，Cookie、Token、Authorization、密码等内容不会以明文写入日志。
- 使用 HTTP 刷新时，如需显式配置 Cookie Header，可填写 `cookie: ${secret.cookie}`；建议优先使用占位符，不要把真实 Cookie 固定写在请求模板中。
