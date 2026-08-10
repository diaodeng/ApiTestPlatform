-- 2026-08-05 统一凭证管理模块
-- 本脚本不迁移旧 hrm.web.browser.session.* 或 hrm.web.runtime.profile.* 数据；请在新模块重新配置。

CREATE TABLE IF NOT EXISTS auth_credential (
  credential_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '凭证主键',
  credential_name VARCHAR(128) NOT NULL COMMENT '凭证名称',
  credential_type VARCHAR(32) NOT NULL COMMENT '凭证类型：browser_storage/http_cookie/http_token/http_api_key/http_header',
  auth_mode VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '认证方式：manual/http_login/http_refresh/browser_login/browser_refresh',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  auto_refresh_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否自动刷新',
  refresh_interval_sec INT NOT NULL DEFAULT 0 COMMENT '自动刷新最小间隔秒数',
  sharing_mode VARCHAR(32) NOT NULL DEFAULT 'shared_read' COMMENT '并发策略：shared_read/exclusive_refresh/exclusive_use',
  secret_cipher_text LONGTEXT NOT NULL COMMENT '凭证内容密文JSON',
  secret_mask VARCHAR(255) NOT NULL DEFAULT '' COMMENT '凭证内容脱敏摘要',
  revision INT NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  expire_time DATETIME NULL COMMENT '凭证到期时间',
  last_refresh_time DATETIME NULL COMMENT '最近成功刷新时间',
  last_refresh_status VARCHAR(32) NOT NULL DEFAULT 'never' COMMENT '最近刷新状态',
  last_refresh_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '最近刷新结果',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  remark VARCHAR(500) NULL COMMENT '备注',
  del_flag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标志：0存在 2删除',
  PRIMARY KEY (credential_id), KEY idx_auth_credential_enabled (enabled, del_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一凭证主表';

CREATE TABLE IF NOT EXISTS auth_credential_auth_config (
  auth_config_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '认证配置主键',
  credential_id BIGINT NOT NULL COMMENT '凭证主键',
  login_url VARCHAR(1000) NOT NULL DEFAULT '',
  refresh_url VARCHAR(1000) NOT NULL DEFAULT '',
  request_method VARCHAR(16) NOT NULL DEFAULT 'POST',
  request_template JSON NULL,
  response_mapping JSON NULL,
  browser_start_url VARCHAR(1000) NOT NULL DEFAULT '',
  otp_type VARCHAR(32) NOT NULL DEFAULT 'none',
  target_host_patterns JSON NULL,
  login_method VARCHAR(16) NOT NULL DEFAULT 'POST' COMMENT '登录请求方法',
  refresh_method VARCHAR(16) NOT NULL DEFAULT 'POST' COMMENT '刷新请求方法',
  login_request_template JSON NULL COMMENT '登录请求模板',
  login_response_mapping JSON NULL COMMENT '登录响应映射',
  login_success_assertions JSON NULL COMMENT '登录成功断言',
  refresh_request_template JSON NULL COMMENT '刷新请求模板',
  refresh_response_mapping JSON NULL COMMENT '刷新响应映射',
  refresh_success_assertions JSON NULL COMMENT '刷新成功断言',
  update_time DATETIME NOT NULL COMMENT '更新时间', PRIMARY KEY (auth_config_id), UNIQUE KEY uk_auth_credential_auth_config (credential_id),
  CONSTRAINT fk_auth_credential_auth_config_credential FOREIGN KEY (credential_id) REFERENCES auth_credential(credential_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一凭证认证与刷新配置';

CREATE TABLE IF NOT EXISTS auth_credential_binding (
  binding_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '绑定主键',
  binding_name VARCHAR(128) NOT NULL COMMENT '绑定名称',
  credential_id BIGINT NOT NULL COMMENT '凭证主键',
  business_type VARCHAR(32) NOT NULL COMMENT '业务类型：web_case/ticket_log_pull/ticket_remote_sync',
  projection_type VARCHAR(32) NOT NULL COMMENT '投影类型：playwright_storage/http_cookie/http_header',
  target_url VARCHAR(1000) NOT NULL DEFAULT '',
  target_host_patterns JSON NULL,
  sharing_mode VARCHAR(32) NOT NULL DEFAULT 'shared_read',
  writeback_enabled TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否允许客户端回写凭证',
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  create_by VARCHAR(64) NOT NULL DEFAULT '',
  create_time DATETIME NOT NULL,
  update_by VARCHAR(64) NOT NULL DEFAULT '',
  update_time DATETIME NOT NULL,
  remark VARCHAR(500) NULL,
  del_flag CHAR(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (binding_id), KEY idx_auth_credential_binding_business (business_type, enabled, del_flag),
  CONSTRAINT fk_auth_credential_binding_credential FOREIGN KEY (credential_id) REFERENCES auth_credential(credential_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一凭证业务绑定表';

CREATE TABLE IF NOT EXISTS auth_credential_operation_log (
  operation_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '操作日志主键', credential_id BIGINT NOT NULL, binding_id BIGINT NULL, operation_type VARCHAR(32) NOT NULL, status VARCHAR(32) NOT NULL,
  revision INT NULL, message VARCHAR(1000) NOT NULL DEFAULT '', operator VARCHAR(64) NOT NULL DEFAULT 'system', create_time DATETIME NOT NULL,
  PRIMARY KEY (operation_id), KEY idx_auth_credential_operation_log_credential (credential_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一凭证操作审计日志';

CREATE TABLE IF NOT EXISTS auth_credential_lease (
  lease_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '租约主键', credential_id BIGINT NOT NULL, lease_token VARCHAR(64) NOT NULL, lease_type VARCHAR(32) NOT NULL, holder VARCHAR(128) NOT NULL, expires_at DATETIME NOT NULL, create_time DATETIME NOT NULL,
  PRIMARY KEY (lease_id), UNIQUE KEY uk_auth_credential_lease_token (lease_token), KEY idx_auth_credential_lease_active (credential_id, lease_type, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一凭证独占租约表';
