-- 2026-07-29 项目版本中心与发布记录
-- 说明：按 MySQL 8 语法编写。执行前请确认目标环境尚未创建同名字段、表和索引。
-- 版本主数据是唯一来源；本脚本仅建立迁移所需的临时文本列关联，后续由仅 ID 脚本删除。

CREATE TABLE ticket_version (
    version_id BIGINT NOT NULL COMMENT '版本ID',
    project_id BIGINT NOT NULL COMMENT '所属项目ID',
    project_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '所属项目名称',
    version_key VARCHAR(100) NOT NULL COMMENT '规范化版本标识',
    version_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '版本展示名称',
    lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'discovered' COMMENT '版本状态：discovered/confirmed/deprecated',
    source VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '首次来源',
    raw_version VARCHAR(200) NULL DEFAULT '' COMMENT '首次发现原始版本文本',
    first_ticket_id BIGINT NULL COMMENT '首次发现工单ID',
    first_detected_at DATETIME NULL COMMENT '首次发现时间',
    planned_release_at DATETIME NULL COMMENT '计划发布时间',
    default_branch VARCHAR(200) NULL DEFAULT '' COMMENT '默认代码分支',
    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否可选',
    remark TEXT NULL COMMENT '备注',
    create_by VARCHAR(100) NULL DEFAULT '' COMMENT '创建者',
    update_by VARCHAR(100) NULL DEFAULT '' COMMENT '更新者',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (version_id),
    UNIQUE KEY uk_ticket_version_project_key (project_id, version_key),
    KEY idx_ticket_version_project_status (project_id, lifecycle_status, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单项目版本中心';

CREATE TABLE ticket_version_release (
    release_id BIGINT NOT NULL COMMENT '发布记录ID',
    version_id BIGINT NOT NULL COMMENT '版本ID',
    environment VARCHAR(64) NOT NULL DEFAULT 'production' COMMENT '发布环境',
    batch_no VARCHAR(64) NOT NULL DEFAULT 'default' COMMENT '发布批次',
    release_status VARCHAR(32) NOT NULL DEFAULT 'planned' COMMENT '发布状态：planned/released/rolled_back',
    planned_release_at DATETIME NULL COMMENT '计划发布时间',
    released_at DATETIME NULL COMMENT '实际发布时间',
    rollback_at DATETIME NULL COMMENT '回滚时间',
    release_by VARCHAR(100) NULL DEFAULT '' COMMENT '发布人',
    ci_url VARCHAR(1000) NULL DEFAULT '' COMMENT 'CI/CD 链接',
    remark TEXT NULL COMMENT '发布说明',
    create_by VARCHAR(100) NULL DEFAULT '' COMMENT '创建者',
    update_by VARCHAR(100) NULL DEFAULT '' COMMENT '更新者',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (release_id),
    UNIQUE KEY uk_ticket_version_release_batch (version_id, environment, batch_no),
    KEY idx_ticket_version_release_version_time (version_id, released_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单版本发布事实记录';

ALTER TABLE ticket
    ADD COLUMN affected_version_id BIGINT NULL COMMENT '发生版本中心ID' AFTER affected_version,
    ADD COLUMN planned_fix_version_id BIGINT NULL COMMENT '计划修复版本中心ID' AFTER planned_fix_version,
    ADD COLUMN fixed_version_id BIGINT NULL COMMENT '实际修复版本中心ID' AFTER fixed_version,
    ADD COLUMN released_version_id BIGINT NULL COMMENT '实际发版版本中心ID' AFTER released_version;

CREATE INDEX idx_ticket_del_affected_version_id ON ticket (del_flag, affected_version_id, ticket_id);
CREATE INDEX idx_ticket_del_planned_fix_version_id ON ticket (del_flag, planned_fix_version_id, ticket_id);
CREATE INDEX idx_ticket_del_fixed_version_id ON ticket (del_flag, fixed_version_id, ticket_id);
CREATE INDEX idx_ticket_del_released_version_id ON ticket (del_flag, released_version_id, ticket_id);

ALTER TABLE ticket_ai_repo_mapping
    ADD COLUMN version_id BIGINT NULL COMMENT '版本中心ID' AFTER project_name;
CREATE INDEX idx_ticket_ai_repo_mapping_version_enabled ON ticket_ai_repo_mapping (version_id, enabled);

-- 从历史工单文本初始化版本中心；未绑定有效项目的历史版本不自动创建，保留原文本等待人工归属。
INSERT INTO ticket_version (
    version_id, project_id, project_name, version_key, version_name,
    lifecycle_status, source, raw_version, first_ticket_id, first_detected_at,
    enabled, create_by, update_by, create_time, update_time
)
SELECT
    UUID_SHORT(), source_rows.project_id, MAX(source_rows.project_name), source_rows.version_key, source_rows.version_key,
    'discovered', 'migration', source_rows.version_key, MIN(source_rows.ticket_id), NOW(),
    1, 'system', 'system', NOW(), NOW()
FROM (
    SELECT ticket_id, project_id, merchant_name AS project_name, NULLIF(TRIM(affected_version), '') AS version_key FROM ticket
    UNION ALL
    SELECT ticket_id, project_id, merchant_name AS project_name, NULLIF(TRIM(planned_fix_version), '') AS version_key FROM ticket
    UNION ALL
    SELECT ticket_id, project_id, merchant_name AS project_name, NULLIF(TRIM(fixed_version), '') AS version_key FROM ticket
    UNION ALL
    SELECT ticket_id, project_id, merchant_name AS project_name, NULLIF(TRIM(released_version), '') AS version_key FROM ticket
) AS source_rows
WHERE source_rows.project_id IS NOT NULL AND source_rows.version_key IS NOT NULL
GROUP BY source_rows.project_id, source_rows.version_key
ON DUPLICATE KEY UPDATE update_time = VALUES(update_time);

UPDATE ticket t
LEFT JOIN ticket_version affected ON affected.project_id = t.project_id
    AND affected.version_key COLLATE utf8mb4_unicode_ci = NULLIF(TRIM(t.affected_version), '') COLLATE utf8mb4_unicode_ci
LEFT JOIN ticket_version planned ON planned.project_id = t.project_id
    AND planned.version_key COLLATE utf8mb4_unicode_ci = NULLIF(TRIM(t.planned_fix_version), '') COLLATE utf8mb4_unicode_ci
LEFT JOIN ticket_version fixed ON fixed.project_id = t.project_id
    AND fixed.version_key COLLATE utf8mb4_unicode_ci = NULLIF(TRIM(t.fixed_version), '') COLLATE utf8mb4_unicode_ci
LEFT JOIN ticket_version released ON released.project_id = t.project_id
    AND released.version_key COLLATE utf8mb4_unicode_ci = NULLIF(TRIM(t.released_version), '') COLLATE utf8mb4_unicode_ci
SET
    t.affected_version_id = affected.version_id,
    t.planned_fix_version_id = planned.version_id,
    t.fixed_version_id = fixed.version_id,
    t.released_version_id = released.version_id;

-- 既有 AI 仓库映射绑定到同项目的版本中心；没有对应工单版本的映射会在服务启动后的首次保存时创建候选版本。
UPDATE ticket_ai_repo_mapping mapping
JOIN ticket_version version_center
    ON version_center.project_id = mapping.project_id
    AND version_center.version_key COLLATE utf8mb4_unicode_ci = mapping.version_key COLLATE utf8mb4_unicode_ci
SET mapping.version_id = version_center.version_id
WHERE mapping.version_id IS NULL;
