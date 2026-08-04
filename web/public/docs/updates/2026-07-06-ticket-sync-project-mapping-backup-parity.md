# 2026-07-06 工单同步项目映射拆分前逻辑对齐

## 背景

对照备份分支 `master_params_ticket_back`（提交 `a69c82a259f3105c90526c097255c8e1cdcbf47a`）梳理工单入库项目/模块识别逻辑。目标是拆分后 `TicketSyncAutomationService.detect_fields` 的实际行为与拆分前 `TicketSyncService._detect_fields` 保持一致。

## 拆分前顺序

1. 项目优先读取外部字段 `ticketVender`，按 `ticket.sync.automation.projectMappings` 做包含匹配。
2. `ticketVender` 未命中有效 HRM 项目时，如果同步模型携带 `projectCode/project_code`，按 HRM 项目业务码匹配。
3. 仅在外部映射场景下，仍未命中项目且携带 `projectId` 时，允许按当前环境项目 ID 兜底。
4. 模块优先读取外部字段 `ticketModle`，按 `ticket.sync.automation.moduleMappings` 做包含匹配。
5. `ticketModle` 未命中有效 HRM 模块时，如果同步模型携带 `moduleCode/module_code`，按 HRM 模块业务码匹配；若已命中项目，会限制在该项目下查找模块。
6. 仅在外部映射场景下，仍未命中模块且携带 `moduleId` 时，允许按当前环境模块 ID 兜底。
7. 不存在“按标题/描述全文匹配项目映射”的逻辑，避免描述中的关键字误绑定项目。

## 本次调整

- 移除错误新增的项目全文映射兜底。
- 恢复 `projectCode/moduleCode` 在 `ticketVender/ticketModle` 映射未命中后的业务码兜底顺序。
- 新增单测覆盖外部同步和 `remote_pull` 两条链路的业务码兜底。

## 验证

- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
- `uv run ruff check modules/ticket/service/sync/ticket_sync_field_mapping_service.py modules/ticket/service/sync/ticket_sync_automation_service.py tests/test_ticket_sync_mapping_boundary.py`
