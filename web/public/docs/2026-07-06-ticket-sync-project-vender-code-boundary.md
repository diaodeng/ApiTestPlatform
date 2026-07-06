# 2026-07-06 工单同步项目映射边界修正

## 背景

工单拆分后需要保持外部入库项目识别边界清晰：第三方外部推送和飞书多维表格主动拉取都应按外部字段 `ticketVender` 命中 `ticket.sync.automation.projectMappings`，不能因为载荷中出现 `projectCode/moduleCode` 就直接绑定本地 HRM 项目或模块。

`projectCode/moduleCode` 只用于内网拉取公网 pending 工单后的本地再入库场景，用来解决跨环境 ID 不一致问题。

## 调整

1. 外部推送和飞书多维表格主动拉取：
   - 项目只通过 `ticketVender` 匹配 `projectMappings`。
   - 模块只通过 `ticketModle` 匹配 `moduleMappings`。
   - 未命中时保留外部原始项目/模块文本，不使用 `projectCode/moduleCode` 绑定本地 ID。
2. 内网拉取外部数据（`remote_pull`）：
   - 保留 `projectCode/moduleCode` 匹配本地 HRM 项目/模块的逻辑。
   - 不复用公网环境的 `projectId/moduleId`。
3. 移除错误的“按工单全文匹配项目映射”兜底，避免描述或标题中的关键字误把工单归属到错误项目。

## 验证

- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_external_detection_ignores_project_and_module_code tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_remote_pull_detection_uses_project_and_module_code`
- `uv run ruff check modules/ticket/service/sync/ticket_sync_field_mapping_service.py modules/ticket/service/sync/ticket_sync_automation_service.py tests/test_ticket_sync_mapping_boundary.py`
