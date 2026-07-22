-- 日志拉取商家配置：商家由系统参数维护，门店仍由 ticket_log_pull_store_config 维护。
-- 请在系统参数配置中将 [] 更新为实际商家，例如：
-- [{"venderNo":"10001","vendorName":"华东商家"}]
INSERT INTO sys_config (
    config_name,
    config_key,
    config_value,
    config_type,
    create_by,
    update_by,
    create_time,
    update_time,
    remark
)
SELECT
    '工单日志拉取商家配置',
    'ticket.logPull.vendors',
    '[]',
    'N',
    'system',
    'system',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    '工单日志拉取商家配置，格式：[{"venderNo":"商户编号","vendorName":"商家名称"}]'
WHERE NOT EXISTS (
    SELECT 1 FROM sys_config WHERE config_key = 'ticket.logPull.vendors'
);
