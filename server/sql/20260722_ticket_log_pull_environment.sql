-- 日志拉取记录新增环境标识字段
-- 支持多环境配置后，记录每次拉取使用的环境信息
ALTER TABLE ticket_log_pull_record
    ADD COLUMN environment VARCHAR(50) NULL COMMENT '拉取时使用的环境标识'
    AFTER ticket_id;
