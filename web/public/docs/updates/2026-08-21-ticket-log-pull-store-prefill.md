# 工单日志拉取门店回填修复

## 变更内容

- 修复工单详情使用轻量概览接口时，日志拉取门店回填信息被摘要响应模型过滤的问题。
- 兼容历史同步数据中的 `external_field_mapping.ticketStore` 原始门店值。
- 门店命中配置时统一归一化为提交用 `org_no`，并通过选项标签展示门店名称、`org_no` 和 `sap_org_no`。
- 门店未命中时继续原样保留输入值，方便用户手动修改和完善。

## 数据口径

- `ticket.extra_data` 保存工单同步门店提示、外部来源快照和自动日志配置。
- `ticket_log_pull_store_config.sap_org_no` 仅用于匹配和搜索；`ticket_log_pull_store_config.org_no` 是日志拉取外部接口的最终 `storeId`。
- `ticket_log_pull_record.store_id` 保存已提交任务的 `org_no`。
