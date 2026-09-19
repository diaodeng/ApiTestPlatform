-- 2026-09-19 配置任务运行实例表
-- 创建时冻结版本快照与输入资源，运行后只追加状态与结果，不回写版本。

CREATE TABLE IF NOT EXISTS configuration_task_run (
  task_run_id BIGINT NOT NULL COMMENT '运行ID，Snowflake BIGINT',
  task_id BIGINT NOT NULL COMMENT '任务ID',
  task_version_id BIGINT NOT NULL COMMENT '执行版本ID',
  version_no INT NOT NULL DEFAULT 1 COMMENT '执行版本号',
  agent_code VARCHAR(128) NOT NULL COMMENT '执行Agent编码',
  trigger_type VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '触发类型',
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '运行状态：PENDING/RUNNING/SUCCESS/FAILED/CANCELLED',
  input_snapshot_json TEXT NOT NULL COMMENT '输入资源快照JSON',
  run_params_json TEXT NOT NULL COMMENT '运行参数快照JSON',
  result_json TEXT NULL COMMENT 'Agent执行结果JSON',
  error_code VARCHAR(64) NOT NULL DEFAULT '' COMMENT '错误码',
  error_message TEXT NULL COMMENT '错误消息',
  started_at DATETIME NULL COMMENT '开始时间',
  ended_at DATETIME NULL COMMENT '结束时间',
  duration_ms INT NOT NULL DEFAULT 0 COMMENT '执行时长毫秒',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  PRIMARY KEY (task_run_id),
  KEY idx_ct_run_task_time (task_id, started_at),
  KEY idx_ct_run_agent_status (agent_code, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务运行实例';
