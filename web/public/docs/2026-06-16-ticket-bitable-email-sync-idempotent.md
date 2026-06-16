# 工单多维表格邮箱同步幂等优化

## 背景

外部推单入库时，`externalSyncBitable.enabled` 开启后会按外部 `recordId` 查询飞书多维表格，补齐报告人、当前负责人、内部负责人邮箱。此前同一工单重复推送时，即使上一次已经成功补齐同一个 `recordId` 的邮箱，也会再次请求多维表格。

## 变更

1. 多维表格邮箱补齐成功后，在 `ticket.extra_data.external_sync.bitableEmailSync` 写入成功状态：
   - `status=success`
   - `recordId`
   - `emailKeys`
   - `syncedAt`
2. 后续同一工单再次外部推送时，如果已有 `bitableEmailSync.status=success` 且 `recordId` 与本次一致，则跳过飞书多维表格查询。
3. 推送侧是否查询多维表格仍由 `ticket.sync.automation.externalSyncBitable.enabled` 控制。
4. 拉取侧是否执行远端拉取仍由 `ticket.sync.automation.remoteSync.enabled` 控制；远端拉取入库不会再次查询公网多维表格，只使用远端 payload 中已携带的邮箱/姓名，并按内网 `assigneeMappings` 或本地邮箱用户匹配解析人员。

## 影响

- 同一 `recordId` 重复推送不会重复调用飞书多维表格接口。
- 新 `recordId`、首次同步失败或未提取到邮箱时，后续推送仍会继续尝试补齐。
- 公网推送补齐后的邮箱会随 pending payload 进入内网，内网拉取只做本地人员解析，不依赖公网多维配置。

## 验证

- 已执行 `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`。
- 已执行 `uv run ruff check modules\ticket\service\ticket_sync_service.py tests\test_ticket_sync_mapping_boundary.py`。
- 已执行 `uv run python -m py_compile modules\ticket\service\ticket_sync_service.py tests\test_ticket_sync_mapping_boundary.py`。
