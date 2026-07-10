-- 2026-07-10 工单统计第三阶段补齐：项目/模块/工单类型维度快照
-- 说明：
-- 1. 在自然日全局快照基础上增加 leaf 维度行，维度为 project_id + module_id + issue_type_id。
-- 2. 历史全局行统一标记 snapshot_scope='all'，维度字段归一为 0 或空字符串。
-- 3. MySQL 8.0 支持 IF EXISTS / IF NOT EXISTS；低版本执行前请先通过 information_schema 检查。

ALTER TABLE ticket_statistics_daily
    ADD COLUMN snapshot_scope VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT '快照范围：all全局，leaf项目模块问题类型明细' AFTER statistics_date,
    ADD COLUMN project_id BIGINT NOT NULL DEFAULT 0 COMMENT '项目ID，0表示全局或未归属' AFTER snapshot_scope,
    ADD COLUMN project_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '项目名称快照' AFTER project_id,
    ADD COLUMN module_id BIGINT NOT NULL DEFAULT 0 COMMENT '模块ID，0表示全局或未归属' AFTER project_name,
    ADD COLUMN module_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '模块名称快照' AFTER module_id,
    ADD COLUMN module_code VARCHAR(128) NOT NULL DEFAULT '' COMMENT '模块业务码快照' AFTER module_name,
    ADD COLUMN issue_type_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '工单类型编码，空表示全局或未填写' AFTER module_code,
    ADD COLUMN issue_type_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '工单类型名称快照' AFTER issue_type_id;

UPDATE ticket_statistics_daily
SET snapshot_scope = 'all',
    project_id = 0,
    project_name = '',
    module_id = 0,
    module_name = '',
    module_code = '',
    issue_type_id = '',
    issue_type_name = ''
WHERE snapshot_scope IS NULL OR snapshot_scope = '';

ALTER TABLE ticket_statistics_daily DROP INDEX uk_ticket_statistics_daily_date;
ALTER TABLE ticket_statistics_daily DROP INDEX idx_ticket_statistics_daily_date;

CREATE UNIQUE INDEX uk_ticket_statistics_daily_scope
    ON ticket_statistics_daily (statistics_date, snapshot_scope, project_id, module_id, issue_type_id);
CREATE INDEX idx_ticket_statistics_daily_date
    ON ticket_statistics_daily (statistics_date);
CREATE INDEX idx_ticket_statistics_daily_scope_date
    ON ticket_statistics_daily (snapshot_scope, statistics_date);
CREATE INDEX idx_ticket_statistics_daily_project
    ON ticket_statistics_daily (statistics_date, project_id);
CREATE INDEX idx_ticket_statistics_daily_module
    ON ticket_statistics_daily (statistics_date, module_id, module_code);
CREATE INDEX idx_ticket_statistics_daily_issue_type
    ON ticket_statistics_daily (statistics_date, issue_type_id);
