# 2026-07-01 飞书多维表格主动拉取分页循环修复

## 背景

主动拉取工单数据时，飞书多维表格 `records/search` 返回的数据量存在分页。现场日志显示请求体中虽然带了 `page_size=200` 和固定 `page_token`，但累计条数按 500 条递增，并且 `page_token` 长时间不变化，说明分页参数未被飞书按预期消费，存在重复拉取同一页并循环到 `max_pages` 的风险。

## 变更内容

1. `TicketSyncNotifyService.query_bitable_records` 将 `page_size`、`page_token` 和 `with_shared_url` 放到 URL 查询参数。
2. `view_id`、`filter`、`with_shared_url` 和 `view_type` 继续保留在 `records/search` 请求体中，避免影响现有过滤条件。
3. 分页日志新增 `page_size`、`page_records` 和 `accumulated`，便于判断每页真实返回数量。
4. 新增已见 `page_token` 检测：飞书再次返回已请求过的分页令牌时，记录 warning 并停止继续拉取，避免同一页无限循环。

## 影响范围

- 主动拉取、按人催办和汇总统计中复用 `query_bitable_records` 的飞书多维表格查询链路都会使用新的分页参数位置。
- 过滤条件结构、字段映射、入库去重和记录详情链接补齐逻辑不变。

## 验证

已新增单元测试覆盖：

1. 分页参数进入 `_request_feishu_json(..., params=...)`，不再进入 JSON body。
2. 第二页请求会携带上一页返回的 `page_token`。
3. 飞书返回重复 `page_token` 时停止请求，避免无限循环。
