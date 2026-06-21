# 2026-06-22 工单飞书多维表格记录链接修复

## 背景

`TicketSyncService._build_bitable_record_url` 之前直接使用飞书多维表格搜索结果中的 `record_id` 拼接：

- `https://feishu.cn/base/{appToken}?table={tableId}&view={viewId}&record={record_id}`

该链接在当前业务场景下不可访问，因为飞书记录详情页实际需要的是记录详情地址，常见形式例如：

- `https://duodian.feishu.cn/record/RotorqQTyeb46qc3BzPcrcvSnSh`

这里的 `RotorqQTyeb46qc3BzPcrcvSnSh` 不是搜索结果里的 `record_id`，继续使用 `record_id` 拼接会把错误链接写入工单详情和催办消息。

## 根因

根据飞书开放平台“查询记录”接口说明：

- 搜索记录接口响应体会直接返回 `record_url`
- 还可能返回 `shared_url`

但在当前 dev 环境实测中：

- `records/search` 即使传入 `with_shared_url=true`，仍只返回 `fields + record_id`
- `records/batch_get` 传入同一批 `record_id` 并开启 `with_shared_url=true`，可以稳定返回 `shared_url`

因此最终适配方案改为：

- 先走 `records/search`
- 对缺少 `record_url/shared_url` 的记录，再批量调用 `records/batch_get`
- 将返回的 `shared_url` 合并回搜索结果

## 本次修复

### 1. 主动拉取链路

- `TicketSyncService._build_bitable_pull_sync_object`
- 优先读取飞书搜索结果中已经补齐的 `record_url/shared_url`
- 写入：
  - `ticketUrl`
  - `source.recordUrl`
  - `raw_payload.recordUrl`

### 2. 按人催办链路

- `TicketSyncNotifyService._collect_person_overdue_data`
- 每条多维记录优先读取搜索后批量补齐的 `record_url/shared_url`
- 本地工单没有 `ticket_url` 时，催办明细 `detailUrl` 回退到飞书返回的真实记录详情地址

### 2.1 搜索结果补链接适配

- `TicketSyncNotifyService.query_bitable_records`
- 搜索结束后自动识别缺少链接的 `record_id`
- 通过 `records/batch_get` 分批补查 `shared_url`
- 每批最多查询 100 条，不做任何写操作

### 3. 兜底策略调整

- 当只有 `record_id`、没有飞书返回的 `record_url/shared_url` 时，不再伪造不可访问的 `...?record=record_id` 链接
- 此时返回空字符串，避免错误链接继续扩散到通知消息和工单详情

## 影响范围

- 飞书多维表格主动拉取入库后的 `ticket_url`
- 外部同步来源信息中的 `source.recordUrl`
- 按人催办消息中的明细详情链接

## 验证点

- 搜索结果含 `record_url` 时，工单同步对象中的 `ticket_url` 应直接使用该值
- 搜索结果不含链接时，应自动通过 `batch_get` 补齐 `shared_url`
- 本地工单无详情链接时，按人催办明细应显示飞书返回的 `record_url`
- 仅有 `record_id` 时，不应再生成旧的 `feishu.cn/base?...&record=...` 假链接

## Dev 实测

使用 dev 环境当前系统参数 `ticket.sync.automation` 中的多维表格配置实测：

- `appToken`: `CMGQwdqKKiWkcRkeP1scq9xvnuc`
- `tableId`: `tblI4sZg9UwCFKxl`
- `viewId`: `vewFuJXaR3`

结果：

- `records/search` 返回 31 条记录，但首条仅含 `record_id=recviUJmmSdE9g`
- `records/batch_get` 可为这 31 条记录全部补回 `shared_url`
- 示例补查结果：`https://duodian.feishu.cn/record/FUY1rD5Cte98g0cx6qYcEOTYnBh`
