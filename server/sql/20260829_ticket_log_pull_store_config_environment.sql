-- 日志拉取门店配置新增环境字段
-- 门店配置按环境分组 key（ticket.logPull.external 的分组 key，如 prod/uat）隔离，
-- 同一门店（vender_no + org_no + sap_org_no）可在不同环境下各存一条。
-- 存量数据环境置空字符串，仅能被"全部环境"查询与显式空环境链路命中。
ALTER TABLE ticket_log_pull_store_config
    ADD COLUMN environment VARCHAR(50) NOT NULL DEFAULT '' COMMENT '环境分组key，来自日志拉取外部接口配置的分组'
    AFTER group_no;

CREATE INDEX idx_ticket_log_pull_store_config_environment
    ON ticket_log_pull_store_config (environment);
