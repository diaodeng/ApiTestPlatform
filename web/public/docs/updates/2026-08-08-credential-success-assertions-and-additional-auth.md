# 2026-08-08 凭证成功断言与附加认证信息

- 凭证表单改为主凭证常显、附加认证信息按需折叠展开；不使用多层 Tab。
- 新增附加 Header、附加 Cookie 的键值对编辑，并阻止主 `Cookie` Header 与结构化附加 Cookie 同时配置；历史冲突数据仍可通过删除图标清理后保存。
- 编辑凭证会回填已保存值，敏感输入框默认掩码显示，可通过眼睛图标查看。
- HTTP 登录、HTTP 刷新新增独立成功断言：HTTP 2xx 后必须通过全部业务断言，才会执行响应提取和写回。
- 切换凭证类型保存时清除旧类型主凭证，避免刷新或业务使用时同时携带已失效的主 Header、Cookie 或 Token。
- 已部署旧表的环境需要执行 `server/sql/20260808_credential_response_success_assertions.sql`。
