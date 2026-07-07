-- 2026-07-08 工单提交时间、处理结论时间和版本治理字段
-- 说明：脚本按 MySQL 8 语法编写；执行前请在目标环境确认字段和索引不存在。

ALTER TABLE ticket
    ADD COLUMN submit_time DATETIME NULL COMMENT '工单业务提交时间' AFTER solution,
    ADD COLUMN affected_version VARCHAR(100) NULL DEFAULT '' COMMENT '问题发生或分析版本' AFTER problem_pattern_verified_at,
    ADD COLUMN planned_fix_version VARCHAR(100) NULL DEFAULT '' COMMENT '计划修复版本' AFTER affected_version,
    ADD COLUMN fixed_version VARCHAR(100) NULL DEFAULT '' COMMENT '实际修复版本' AFTER planned_fix_version,
    ADD COLUMN released_version VARCHAR(100) NULL DEFAULT '' COMMENT '实际发版版本' AFTER fixed_version,
    ADD COLUMN processed_at DATETIME NULL COMMENT '首次形成处理结论时间' AFTER first_response_at,
    ADD COLUMN released_at DATETIME NULL COMMENT '实际发版时间' AFTER processed_at,
    ADD COLUMN verified_at DATETIME NULL COMMENT '验证完成时间' AFTER released_at;

CREATE INDEX idx_ticket_del_submit_time ON ticket (del_flag, submit_time, ticket_id);
CREATE INDEX idx_ticket_del_processed_time ON ticket (del_flag, processed_at, ticket_id);
CREATE INDEX idx_ticket_del_resolved_time ON ticket (del_flag, resolved_at, ticket_id);
CREATE INDEX idx_ticket_del_closed_time ON ticket (del_flag, closed_at, ticket_id);
CREATE INDEX idx_ticket_del_planned_fix_version ON ticket (del_flag, planned_fix_version, ticket_id);

UPDATE ticket
SET submit_time = COALESCE(
    submit_time,
    STR_TO_DATE(
        REPLACE(
            LEFT(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(extra_data, '$.external_sync.externalCreateTime')), ''), 19),
            'T',
            ' '
        ),
        '%Y-%m-%d %H:%i:%s'
    ),
    STR_TO_DATE(
        REPLACE(
            LEFT(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(extra_data, '$.external_sync.source.externalCreateTime')), ''), 19),
            'T',
            ' '
        ),
        '%Y-%m-%d %H:%i:%s'
    ),
    create_time
)
WHERE submit_time IS NULL;

UPDATE ticket
SET affected_version = COALESCE(
    NULLIF(affected_version, ''),
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(extra_data, '$.version_key')), ''),
    NULLIF(JSON_UNQUOTE(JSON_EXTRACT(extra_data, '$.versionKey')), ''),
    ''
)
WHERE affected_version IS NULL OR affected_version = '';

UPDATE ticket
SET processed_at = COALESCE(processed_at, resolved_at, closed_at)
WHERE processed_at IS NULL
  AND (
    NULLIF(root_cause, '') IS NOT NULL
    OR NULLIF(solution, '') IS NOT NULL
    OR NULLIF(root_cause_type, '') IS NOT NULL
    OR NULLIF(solution_type, '') IS NOT NULL
    OR NULLIF(resolution_code, '') IS NOT NULL
    OR status IN ('wait_release', 'wait_verify', 'resolved', 'closed', 'rejected', 'non_problem', 'design_as_expected', 'user_misoperation', 'duplicated')
  );
