-- 2026-09-19 配置任务资源传输表
-- 记录服务端到 Agent 的受控资源发布传输，不保存文件正文。

CREATE TABLE IF NOT EXISTS configuration_task_resource_transfer (
  transfer_id VARCHAR(128) NOT NULL COMMENT '传输ID',
  resource_id BIGINT NOT NULL COMMENT '资源ID，关联资源对象',
  agent_code VARCHAR(128) NOT NULL COMMENT '目标Agent编码',
  session_id VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'Agent连接会话ID',
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '传输状态',
  expected_size BIGINT NOT NULL DEFAULT 0 COMMENT '预期文件大小',
  expected_sha256 CHAR(64) NOT NULL COMMENT '预期SHA-256',
  version INT NOT NULL DEFAULT 1 COMMENT '资源版本',
  received_bytes BIGINT NOT NULL DEFAULT 0 COMMENT '最近确认接收字节数',
  received_chunks INT NOT NULL DEFAULT 0 COMMENT '最近确认分片数',
  expires_at DATETIME NULL COMMENT '传输过期时间',
  completed_at DATETIME NULL COMMENT '完成时间',
  error_code VARCHAR(64) NOT NULL DEFAULT '' COMMENT '最近错误码',
  error_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '最近错误摘要',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  last_audit_at DATETIME NULL COMMENT '最近审计时间',
  audit_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审计摘要',
  PRIMARY KEY (transfer_id),
  KEY idx_ct_transfer_resource_status (resource_id, status),
  KEY idx_ct_transfer_agent_status (agent_code, status),
  KEY idx_ct_transfer_expire (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务资源传输记录';
