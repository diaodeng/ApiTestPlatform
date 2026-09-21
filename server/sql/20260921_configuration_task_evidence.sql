-- 2026-09-21 配置任务运行取证增量字段
-- 仅增加元数据、快照和引用级幂等约束，不保存截图正文；执行前请确认基线表已存在。
-- 迁移执行顺序：先确认四张基线表和新增字段不存在；已存在字段由迁移工具按幂等规则跳过。
-- 建立唯一索引前必须先人工检查下方重复查询；发现重复时停止迁移并保留业务数据，
-- 由业务负责人确认保留记录后再处理。本文不自动删除、合并或覆盖历史数据。
-- 目标数据库若不支持 ADD COLUMN IF NOT EXISTS，应由发布工具完成字段存在性预检。
-- 兼容 MySQL/MariaDB：TEXT 字段不能声明 DEFAULT；本迁移统一先允许 NULL，回填空 JSON，再收紧为 NOT NULL。

ALTER TABLE configuration_task_stage
  ADD COLUMN step_ids_json TEXT NULL COMMENT '阶段内稳定步骤ID列表JSON',
  ADD COLUMN evidence_policy_json TEXT NULL COMMENT '阶段取证策略JSON';

UPDATE configuration_task_stage
SET step_ids_json = '[]'
WHERE step_ids_json IS NULL;

UPDATE configuration_task_stage
SET evidence_policy_json = '{}'
WHERE evidence_policy_json IS NULL;

ALTER TABLE configuration_task_stage
  MODIFY COLUMN step_ids_json TEXT NOT NULL COMMENT '阶段内稳定步骤ID列表JSON',
  MODIFY COLUMN evidence_policy_json TEXT NOT NULL COMMENT '阶段取证策略JSON';

ALTER TABLE configuration_task_run
  ADD COLUMN business_status VARCHAR(32) NOT NULL DEFAULT 'PENDING' COMMENT '业务执行状态',
  ADD COLUMN evidence_status VARCHAR(32) NOT NULL DEFAULT 'NOT_REQUIRED' COMMENT '证据完整状态',
  ADD COLUMN evidence_missing_json TEXT NULL COMMENT '缺失证据项JSON';

UPDATE configuration_task_run
SET evidence_missing_json = '[]'
WHERE evidence_missing_json IS NULL;

ALTER TABLE configuration_task_run
  MODIFY COLUMN evidence_missing_json TEXT NOT NULL COMMENT '缺失证据项JSON';

ALTER TABLE configuration_task_run_stage
  ADD COLUMN step_ids_json TEXT NULL COMMENT '运行阶段步骤ID快照JSON',
  ADD COLUMN evidence_policy_json TEXT NULL COMMENT '运行阶段取证策略快照JSON',
  ADD COLUMN evidence_status VARCHAR(32) NOT NULL DEFAULT 'NOT_REQUIRED' COMMENT '阶段证据完整状态',
  ADD COLUMN evidence_missing_json TEXT NULL COMMENT '阶段缺失证据项JSON';

UPDATE configuration_task_run_stage
SET step_ids_json = '[]'
WHERE step_ids_json IS NULL;

UPDATE configuration_task_run_stage
SET evidence_policy_json = '{}'
WHERE evidence_policy_json IS NULL;

UPDATE configuration_task_run_stage
SET evidence_missing_json = '[]'
WHERE evidence_missing_json IS NULL;

ALTER TABLE configuration_task_run_stage
  MODIFY COLUMN step_ids_json TEXT NOT NULL COMMENT '运行阶段步骤ID快照JSON',
  MODIFY COLUMN evidence_policy_json TEXT NOT NULL COMMENT '运行阶段取证策略快照JSON',
  MODIFY COLUMN evidence_missing_json TEXT NOT NULL COMMENT '阶段缺失证据项JSON';

ALTER TABLE configuration_task_artifact
  ADD COLUMN step_id VARCHAR(128) NOT NULL DEFAULT '' COMMENT '稳定步骤ID',
  ADD COLUMN evidence_type VARCHAR(64) NOT NULL DEFAULT '' COMMENT '证据类型',
  ADD COLUMN evidence_key VARCHAR(255) NOT NULL DEFAULT '' COMMENT '证据键',
  ADD COLUMN sequence_no INT NOT NULL DEFAULT 1 COMMENT '同一步骤产物顺序',
  ADD COLUMN captured_at DATETIME NULL COMMENT 'Agent采集时间',
  ADD COLUMN mask_applied TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已遮罩',
  ADD COLUMN availability_status VARCHAR(32) NOT NULL DEFAULT 'ONLINE' COMMENT '资源可用状态',
  ADD COLUMN provider_type VARCHAR(32) NOT NULL DEFAULT 'agent_local' COMMENT '资源Provider',
  ADD COLUMN agent_code VARCHAR(128) NOT NULL DEFAULT '' COMMENT '持有资源的Agent',
  ADD COLUMN object_key VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'Agent受控相对定位键',
  ADD COLUMN mime_type VARCHAR(255) NOT NULL DEFAULT '' COMMENT '资源MIME类型';

UPDATE configuration_task_run
SET business_status = status
WHERE business_status = 'PENDING'
  AND status IN ('RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED');

-- 老数据的 step_key 作为兼容步骤身份，避免历史产物在新唯一键中全部冲突。
UPDATE configuration_task_artifact
SET step_id = step_key
WHERE step_id = '' AND step_key <> '';

-- 先清理同一引用身份的历史重复行，再建立数据库级幂等约束。
-- 若线上存在重复数据，应先人工核对保留最早 artifact_id；本语句不自动删除业务数据。
-- 建议执行前运行：
-- SELECT task_run_id, run_stage_id, step_id, evidence_key, sequence_no, sha256, COUNT(*)
-- FROM configuration_task_artifact
-- GROUP BY task_run_id, run_stage_id, step_id, evidence_key, sequence_no, sha256
-- HAVING COUNT(*) > 1;
ALTER TABLE configuration_task_artifact
  ADD UNIQUE KEY uk_ct_artifact_evidence_identity
    (task_run_id, run_stage_id, step_id, evidence_key, sequence_no, sha256);

-- 产物预览/下载审计：只保存标识、动作、结果和脱敏摘要，不保存正文、路径或凭证。
CREATE TABLE configuration_task_artifact_access_audit (
  audit_id BIGINT NOT NULL COMMENT '审计ID，Snowflake BIGINT',
  artifact_id BIGINT NULL COMMENT '产物ID',
  task_run_id BIGINT NULL COMMENT '运行ID',
  resource_id BIGINT NULL COMMENT '资源ID',
  action VARCHAR(16) NOT NULL COMMENT '动作：preview/download',
  operator VARCHAR(64) NOT NULL DEFAULT '' COMMENT '操作者',
  success TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否成功',
  error_code VARCHAR(64) NOT NULL DEFAULT '' COMMENT '稳定错误码',
  audit_message VARCHAR(500) NOT NULL DEFAULT '' COMMENT '脱敏审计摘要',
  create_time DATETIME NOT NULL COMMENT '审计时间',
  PRIMARY KEY (audit_id),
  KEY idx_ct_artifact_access_audit_artifact (artifact_id, create_time),
  KEY idx_ct_artifact_access_audit_run (task_run_id, create_time)
) COMMENT='配置任务产物访问审计';
