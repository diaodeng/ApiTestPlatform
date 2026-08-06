-- 2026-08-06 浏览器凭证回写开关增量迁移。
-- 仅需在已执行 20260805_credential_management.sql 的数据库上执行一次。
ALTER TABLE auth_credential_binding
  ADD COLUMN writeback_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否允许客户端回写凭证'
  AFTER sharing_mode;
