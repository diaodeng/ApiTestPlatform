-- 2026-07-11 工单统计：业务周周期快照
-- 说明：
-- 1. 新增 ticket_statistics_period_snapshot，用于冻结周四 18:00 等非自然日业务周期。
-- 2. 现有 ticket_statistics_daily 继续保留自然日快照；快照口径 + 业务周趋势读取本表。
-- 3. 历史业务周需要通过 module_task.scheduler_maintenance.ticket_business_week_statistics_snapshot 补跑。

CREATE TABLE IF NOT EXISTS ticket_statistics_period_snapshot (
    id BIGINT NOT NULL COMMENT '统计ID',
    period_type VARCHAR(32) NOT NULL DEFAULT 'business_week' COMMENT '周期类型',
    period_key VARCHAR(64) NOT NULL DEFAULT '' COMMENT '周期键，如业务周开始日期',
    period_start_time DATETIME NOT NULL COMMENT '周期开始时间',
    period_end_time DATETIME NOT NULL COMMENT '周期结束时间',
    snapshot_scope VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT '快照范围：all全局，leaf项目模块问题类型明细',
    project_id BIGINT NOT NULL DEFAULT 0 COMMENT '项目ID，0表示全局或未归属',
    project_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '项目名称快照',
    module_id BIGINT NOT NULL DEFAULT 0 COMMENT '模块ID，0表示全局或未归属',
    module_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '模块名称快照',
    module_code VARCHAR(128) NOT NULL DEFAULT '' COMMENT '模块业务码快照',
    issue_type_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '工单类型编码，空表示全局或未填写',
    issue_type_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '工单类型名称快照',
    total_count INT NOT NULL DEFAULT 0 COMMENT '工单总数',
    submitted_count INT NOT NULL DEFAULT 0 COMMENT '新增工单数',
    new_count INT NOT NULL DEFAULT 0 COMMENT '新增工单数（兼容旧字段）',
    first_responded_count INT NOT NULL DEFAULT 0 COMMENT '已响应数',
    processed_count INT NOT NULL DEFAULT 0 COMMENT '已处理数',
    processed_in_new_count INT NOT NULL DEFAULT 0 COMMENT '新增工单已处理数',
    process_rate DOUBLE NOT NULL DEFAULT 0 COMMENT '新增工单处理率',
    resolved_count INT NOT NULL DEFAULT 0 COMMENT '处置完成数',
    closed_count INT NOT NULL DEFAULT 0 COMMENT '关闭数',
    unprocessed_backlog INT NOT NULL DEFAULT 0 COMMENT '周期末未处理存量',
    open_backlog INT NOT NULL DEFAULT 0 COMMENT '周期末未关闭存量',
    avg_first_response_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均首次响应耗时',
    avg_first_process_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均首次处理耗时',
    avg_resolve_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均处置完成耗时',
    avg_close_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均关闭耗时',
    avg_process_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均处理秒数（旧字段，兼容保留）',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_ticket_statistics_period_scope (
        period_type,
        period_start_time,
        snapshot_scope,
        project_id,
        module_id,
        issue_type_id
    ),
    KEY idx_ticket_statistics_period_start (period_type, period_start_time),
    KEY idx_ticket_statistics_period_scope_start (snapshot_scope, period_type, period_start_time),
    KEY idx_ticket_statistics_period_project (period_start_time, project_id),
    KEY idx_ticket_statistics_period_module (period_start_time, module_id, module_code),
    KEY idx_ticket_statistics_period_issue_type (period_start_time, issue_type_id)
) COMMENT='工单周期统计快照表';
