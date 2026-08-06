-- 统一凭证 HTTP 登录/刷新配置拆分。
-- 已执行首版表结构的环境执行本脚本；重复执行前请确认数据库支持 IF NOT EXISTS。
ALTER TABLE auth_credential_auth_config
  ADD COLUMN login_method VARCHAR(16) NOT NULL DEFAULT 'POST' COMMENT '登录请求方法',
  ADD COLUMN refresh_method VARCHAR(16) NOT NULL DEFAULT 'POST' COMMENT '刷新请求方法',
  ADD COLUMN login_request_template JSON NULL COMMENT '登录请求模板',
  ADD COLUMN login_response_mapping JSON NULL COMMENT '登录响应映射',
  ADD COLUMN refresh_request_template JSON NULL COMMENT '刷新请求模板',
  ADD COLUMN refresh_response_mapping JSON NULL COMMENT '刷新响应映射';
