-- 2026-09-19 配置任务阶段与产物表
-- 版本阶段随版本发布冻结；运行阶段创建时快照；产物只追加资源引用，不保存文件正文。

CREATE TABLE IF NOT EXISTS configuration_task_stage (
  stage_id BIGINT NOT NULL COMMENT '阶段ID，Snowflake BIGINT',
  version_id BIGINT NOT NULL COMMENT '任务版本ID',
  stage_key VARCHAR(128) NOT NULL COMMENT '阶段标识，版本内唯一',
  stage_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '阶段名称',
  mode VARCHAR(32) NOT NULL DEFAULT 'READ' COMMENT '阶段模式：READ/PREPARE_WRITE/WRITE/VERIFY',
  stage_order INT NOT NULL DEFAULT 0 COMMENT '阶段顺序，从1递增',
  step_range_json TEXT NOT NULL COMMENT '阶段内步骤索引列表JSON',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (stage_id),
  UNIQUE KEY uk_ct_stage_version_key (version_id, stage_key),
  KEY idx_ct_stage_version_order (version_id, stage_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务版本阶段';

CREATE TABLE IF NOT EXISTS configuration_task_run_stage (
  run_stage_id BIGINT NOT NULL COMMENT '运行阶段ID，Snowflake BIGINT',
  task_run_id BIGINT NOT NULL COMMENT '运行ID',
  stage_id BIGINT NOT NULL COMMENT '来源版本阶段ID',
  stage_key VARCHAR(128) NOT NULL COMMENT '阶段标识',
  stage_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '阶段名称',
  mode VARCHAR(32) NOT NULL DEFAULT 'READ' COMMENT '阶段模式',
  stage_order INT NOT NULL DEFAULT 0 COMMENT '阶段顺序',
  step_range_json TEXT NOT NULL COMMENT '阶段内步骤索引列表JSON',
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '阶段状态',
  result_json TEXT NULL COMMENT '阶段步骤结果JSON',
  error_code VARCHAR(64) NOT NULL DEFAULT '' COMMENT '错误码',
  error_message TEXT NULL COMMENT '错误消息',
  retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
  approved_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'WRITE阶段审批人',
  approved_at DATETIME NULL COMMENT '审批时间',
  started_at DATETIME NULL COMMENT '阶段开始时间',
  ended_at DATETIME NULL COMMENT '阶段结束时间',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  PRIMARY KEY (run_stage_id),
  UNIQUE KEY uk_ct_run_stage_run_key (task_run_id, stage_key),
  KEY idx_ct_run_stage_run_order (task_run_id, stage_order),
  KEY idx_ct_run_stage_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务运行阶段';

CREATE TABLE IF NOT EXISTS configuration_task_artifact (
  artifact_id BIGINT NOT NULL COMMENT '产物ID，Snowflake BIGINT',
  task_run_id BIGINT NOT NULL COMMENT '运行ID',
  run_stage_id BIGINT NULL COMMENT '运行阶段ID',
  artifact_type VARCHAR(32) NOT NULL COMMENT '产物类型：step_screenshot/failure_screenshot/execution_log/report',
  step_key VARCHAR(128) NOT NULL DEFAULT '' COMMENT '关联步骤标识',
  resource_id BIGINT NOT NULL COMMENT '资源对象ID',
  original_file_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '展示文件名',
  file_size BIGINT NOT NULL DEFAULT 0 COMMENT '文件字节数',
  sha256 CHAR(64) NOT NULL DEFAULT '' COMMENT 'SHA-256',
  note VARCHAR(500) NOT NULL DEFAULT '' COMMENT '产物说明',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  PRIMARY KEY (artifact_id),
  KEY idx_ct_artifact_run_stage (task_run_id, run_stage_id),
  KEY idx_ct_artifact_type (artifact_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务运行产物';
