-- 2026-07-29 项目版本中心仅 ID 关联改造
-- 前置条件：已执行 20260729_ticket_version_center.sql。
-- 请先执行本文件中的预检 SELECT；确认未关联数量为 0 后，再执行后续 ALTER TABLE。

-- 为仅存在于 AI 仓库映射中的旧版本文本补齐版本中心记录。
INSERT INTO ticket_version (
    version_id, project_id, project_name, version_key, version_name,
    lifecycle_status, source, raw_version, enabled,
    create_by, update_by, create_time, update_time
)
SELECT
    UUID_SHORT(), mapping.project_id, MAX(mapping.project_name), TRIM(mapping.version_key), TRIM(mapping.version_key),
    'discovered', 'migration', TRIM(mapping.version_key), 1,
    'system', 'system', NOW(), NOW()
FROM ticket_ai_repo_mapping mapping
WHERE mapping.version_id IS NULL
  AND NULLIF(TRIM(mapping.version_key), '') IS NOT NULL
GROUP BY mapping.project_id, TRIM(mapping.version_key)
ON DUPLICATE KEY UPDATE update_time = VALUES(update_time);

UPDATE ticket_ai_repo_mapping mapping
JOIN ticket_version version_center
  ON version_center.project_id = mapping.project_id
 AND version_center.version_key COLLATE utf8mb4_unicode_ci = TRIM(mapping.version_key) COLLATE utf8mb4_unicode_ci
SET mapping.version_id = version_center.version_id
WHERE mapping.version_id IS NULL;

ALTER TABLE ticket_ai_analysis_task
    ADD COLUMN version_id BIGINT NULL COMMENT '版本中心ID' AFTER mapping_id;

UPDATE ticket_ai_analysis_task task
LEFT JOIN ticket_ai_repo_mapping mapping ON mapping.mapping_id = task.mapping_id
LEFT JOIN ticket ON ticket.ticket_id = task.ticket_id
SET task.version_id = COALESCE(mapping.version_id, ticket.affected_version_id)
WHERE task.version_id IS NULL;

-- 预检 1：任何非空工单版本文本都必须已有版本中心 ID。
SELECT ticket_id, ticket_no
FROM ticket
WHERE (NULLIF(TRIM(affected_version), '') IS NOT NULL AND affected_version_id IS NULL)
   OR (NULLIF(TRIM(planned_fix_version), '') IS NOT NULL AND planned_fix_version_id IS NULL)
   OR (NULLIF(TRIM(fixed_version), '') IS NOT NULL AND fixed_version_id IS NULL)
   OR (NULLIF(TRIM(released_version), '') IS NOT NULL AND released_version_id IS NULL);

-- 预检 2：每条仓库映射都必须关联版本中心，空版本映射需人工补齐或删除。
SELECT mapping_id, project_id, project_name, version_key
FROM ticket_ai_repo_mapping
WHERE version_id IS NULL;

-- 预检 3：无法根据原映射或工单发生版本回填的历史 AI 任务需人工补齐或删除。
SELECT task_id, ticket_id, mapping_id
FROM ticket_ai_analysis_task
WHERE version_id IS NULL;

-- 执行以下 DDL 前，以上三条 SELECT 必须均返回 0 行。
ALTER TABLE ticket
    DROP INDEX idx_ticket_del_planned_fix_version,
    DROP COLUMN affected_version,
    DROP COLUMN planned_fix_version,
    DROP COLUMN fixed_version,
    DROP COLUMN released_version;

ALTER TABLE ticket_ai_repo_mapping
    DROP INDEX uk_ticket_ai_repo_mapping_project_version,
    DROP COLUMN version_key,
    MODIFY COLUMN version_id BIGINT NOT NULL COMMENT '版本中心ID',
    ADD UNIQUE KEY uk_ticket_ai_repo_mapping_project_version (project_id, version_id);

ALTER TABLE ticket_ai_analysis_task
    DROP COLUMN version_key,
    MODIFY COLUMN version_id BIGINT NOT NULL COMMENT '版本中心ID',
    ADD KEY idx_ticket_ai_analysis_task_version (version_id);
