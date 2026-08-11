-- 2026-07-10 工单统计第三阶段：快照口径与自然日冻结
-- 说明：
-- 1. 扩展 ticket_statistics_daily，为自然日快照补齐提交、响应、处理率、存量和耗时字段。
-- 2. 新增的任务逻辑已通过 module_task.scheduler_maintenance.ticket_daily_statistics_snapshot
--    注册到 JOB_REGISTRY，celery_tasks/celery_job_service 会自动发现，无需额外新增任务种子记录。
-- 3. 若目标库已存在部分字段，请先按 information_schema 检查后再执行。

ALTER TABLE ticket_statistics_daily
    ADD COLUMN total_count INT NOT NULL DEFAULT 0 COMMENT '工单总数',
    ADD COLUMN submitted_count INT NOT NULL DEFAULT 0 COMMENT '新增工单数',
    ADD COLUMN first_responded_count INT NOT NULL DEFAULT 0 COMMENT '已响应数',
    ADD COLUMN processed_count INT NOT NULL DEFAULT 0 COMMENT '已处理数',
    ADD COLUMN processed_in_new_count INT NOT NULL DEFAULT 0 COMMENT '新增工单已处理数',
    ADD COLUMN process_rate DOUBLE NOT NULL DEFAULT 0 COMMENT '新增工单处理率',
    ADD COLUMN resolved_count INT NOT NULL DEFAULT 0 COMMENT '处置完成数',
    ADD COLUMN closed_count INT NOT NULL DEFAULT 0 COMMENT '关闭数',
    ADD COLUMN unprocessed_backlog INT NOT NULL DEFAULT 0 COMMENT '周期末未处理存量',
    ADD COLUMN open_backlog INT NOT NULL DEFAULT 0 COMMENT '周期末未关闭存量',
    ADD COLUMN avg_first_response_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均首次响应耗时',
    ADD COLUMN avg_first_process_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均首次处理耗时',
    ADD COLUMN avg_resolve_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均处置完成耗时',
    ADD COLUMN avg_close_seconds BIGINT NOT NULL DEFAULT 0 COMMENT '平均关闭耗时';

CREATE UNIQUE INDEX uk_ticket_statistics_daily_date ON ticket_statistics_daily (statistics_date);
CREATE INDEX idx_ticket_statistics_daily_date ON ticket_statistics_daily (statistics_date);
