-- 凭证 HTTP 登录/刷新接口业务成功断言。
-- 已部署旧表的环境执行本脚本；新环境已包含在 20260805_credential_management.sql 中。
ALTER TABLE auth_credential_auth_config
  ADD COLUMN login_success_assertions JSON NULL COMMENT '登录成功断言' AFTER login_response_mapping,
  ADD COLUMN refresh_success_assertions JSON NULL COMMENT '刷新成功断言' AFTER refresh_response_mapping;
