-- 2026-09-19 配置任务资源对象元数据表
-- 首期只保存 Agent 本地资源身份与校验元数据，不实现文件内容传输。

CREATE TABLE IF NOT EXISTS configuration_task_resource_object (
  resource_id BIGINT NOT NULL COMMENT '资源ID，Snowflake BIGINT',
  provider_type VARCHAR(32) NOT NULL DEFAULT 'agent_local' COMMENT '资源Provider：首期仅agent_local',
  provider_execution_side VARCHAR(16) NOT NULL DEFAULT 'agent' COMMENT 'Provider执行侧：agent/server',
  agent_code VARCHAR(128) NOT NULL COMMENT '执行Agent编码',
  object_key VARCHAR(512) NOT NULL COMMENT 'Provider受控相对定位键',
  original_file_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
  mime_type VARCHAR(255) NOT NULL DEFAULT 'application/octet-stream' COMMENT 'MIME类型',
  file_size BIGINT NOT NULL DEFAULT 0 COMMENT '文件字节数',
  checksum_algorithm VARCHAR(16) NOT NULL DEFAULT 'sha256' COMMENT '校验算法',
  sha256 CHAR(64) NOT NULL COMMENT 'SHA-256摘要',
  version INT NOT NULL DEFAULT 1 COMMENT '资源版本',
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '资源状态',
  expires_at DATETIME NULL COMMENT '资源过期时间',
  deleted_at DATETIME NULL COMMENT '资源删除时间',
  error_code VARCHAR(64) NOT NULL DEFAULT '' COMMENT '最近错误码',
  error_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '最近错误摘要',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  last_audit_at DATETIME NULL COMMENT '最近审计时间',
  audit_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审计摘要',
  remark TEXT NULL COMMENT '备注',
  PRIMARY KEY (resource_id),
  KEY idx_ct_resource_agent_status (agent_code, status, resource_id),
  KEY idx_ct_resource_expire (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务资源对象元数据';
