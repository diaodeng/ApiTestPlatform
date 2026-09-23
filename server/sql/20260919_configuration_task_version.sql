-- 2026-09-19 配置任务定义与版本快照表
-- 任务长期可编辑；版本发布后冻结步骤、变量和输入资源绑定，不可原地修改。

CREATE TABLE IF NOT EXISTS configuration_task (
  task_id BIGINT NOT NULL COMMENT '任务ID，Snowflake BIGINT',
  task_name VARCHAR(128) NOT NULL COMMENT '任务名称',
  description VARCHAR(500) NOT NULL DEFAULT '' COMMENT '任务描述',
  agent_code VARCHAR(128) NOT NULL COMMENT '默认执行Agent编码',
  variables_json TEXT NOT NULL COMMENT '业务变量JSON',
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' COMMENT '任务状态：ACTIVE/DISABLED',
  current_version_id BIGINT NULL COMMENT '当前发布版本ID',
  current_version_no INT NULL COMMENT '当前发布版本号',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  remark TEXT NULL COMMENT '备注',
  PRIMARY KEY (task_id),
  KEY idx_ct_task_status (status, task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务定义';

CREATE TABLE IF NOT EXISTS configuration_task_version (
  version_id BIGINT NOT NULL COMMENT '版本ID，Snowflake BIGINT',
  task_id BIGINT NOT NULL COMMENT '任务ID',
  version_no INT NOT NULL DEFAULT 1 COMMENT '版本号，从1递增',
  status VARCHAR(32) NOT NULL DEFAULT 'DRAFT' COMMENT '版本状态：DRAFT/PUBLISHED/DEPRECATED',
  start_url VARCHAR(512) NOT NULL DEFAULT '' COMMENT '起始URL',
  browser_name VARCHAR(32) NOT NULL DEFAULT 'chromium' COMMENT '浏览器名称',
  headless TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否无头模式',
  credential_binding_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '凭证绑定ID',
  variables_json TEXT NOT NULL COMMENT '版本冻结变量JSON',
  steps_json TEXT NOT NULL COMMENT 'Web步骤列表JSON',
  input_bindings_json TEXT NOT NULL COMMENT 'fileKey到资源ID绑定JSON',
  publish_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '发布人',
  publish_time DATETIME NULL COMMENT '发布时间',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  PRIMARY KEY (version_id),
  UNIQUE KEY uk_ct_version_task_no (task_id, version_no),
  KEY idx_ct_version_task_status (task_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务版本快照';
