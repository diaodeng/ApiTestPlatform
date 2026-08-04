# 2026-06-18 工单催办飞书记录链接兜底

## 背景

工单按人催办使用默认模板时，明细行依赖 `detailUrl/detail_link` 输出链接。多维表格数据源场景下，原逻辑只从本地工单库读取 `ticket_url`，如果本地库没有保存对应链接，催办消息中不会出现可点击的工单详情。

## 调整

- `TicketSyncNotifyService.get_bitable_record_url` 增加配置校验：只有 `appToken/tableId/recordId` 齐全时才生成飞书多维表格记录 URL。
- 新增 `_resolve_bitable_reminder_detail_url`：优先使用本地工单 `ticket_url`，本地缺失时根据人员催办配置中的 `appToken/tableId/viewId` 和记录 `recordId` 生成飞书记录 URL。
- 多维表格按人催办明细构造时统一使用上述解析逻辑，默认模板无需单独配置即可通过 `${detail_link}` 输出链接。

## 验证

- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
- `uv run ruff check modules\ticket\service\ticket_sync_notify_service.py tests\test_ticket_sync_mapping_boundary.py`

## 风险

- 兜底链接依赖人员催办配置中的 `appToken/tableId/viewId` 与飞书记录 `recordId`；如果配置错误或记录 ID 缺失，仍会保持无链接。
- 该改动不回写本地 `ticket_url`，只影响催办消息和预览统计中的明细 URL。
