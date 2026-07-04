# 2026-07-04 工单拆分后备份分支逻辑对齐审计

## 背景

本次检查以备份分支 `master_params_ticket_new` 为业务语义基准，核对当前拆分后的工单后端逻辑是否保持一致。重点范围为 `server/modules/ticket/controller`、`server/modules/ticket/service/sync`、`server/module_task/scheduler_maintenance.py` 和工单同步边界测试。

## 对齐结果

1. 主动拉取时间窗口恢复备份分支行为：`autoAppendTimeFilter=true` 时忽略配置或任务覆盖中的 `createdAfter/createdBefore`，每次执行动态生成最近 1 小时窗口。
2. 多维表格主动拉取 filter 构造恢复备份分支行为：无原始 filter 时追加时间条件使用 `and`；嵌套 filter 只在最外层追加 `and` 时间子条件；扁平已有 filter 时不递归补齐原有空时间值。
3. 拆分 controller 后的路由集合已与备份分支一致：总数 86，未缺失旧路由，也无重复路由。
4. 删除 `ticket_crud_controller.py` 中重复注册的 `/ticket/log-pulls` 和 `/ticket/stat-classification/options`，分别保留在日志拉取 controller 与配置 controller 中。
5. 保留拆分后的职责边界：主动拉取、远端拉取、通知任务、同步配置等仍由子服务承接，不恢复 `TicketSyncService` 转发门面。

## 验证

1. `cd server; uv run ruff check modules/ticket/controller/ticket_crud_controller.py modules/ticket/service/sync/ticket_bitable_pull_service.py modules/ticket/service/sync/ticket_sync_config_service.py tests/test_ticket_sync_mapping_boundary.py`
2. `cd server; uv run python -m unittest tests.test_ticket_sync_mapping_boundary -q`
3. 使用脚本对比 `master_params_ticket_new` 的旧 controller 路由与当前拆分 controller 路由，确认 `old=86 current=86 missing=[] duplicates=[]`。
4. 使用服务导入脚本确认 `TicketBitablePullService`、`TicketSyncConfigService` 可导入，并确认默认时间 filter 的连接符为 `and`。

## 注意事项

1. 后续若需要重新启用递归补齐多维表格 filter 时间值，必须作为新需求单独评估，不能伪装为拆分兼容修复。
2. 对照备份分支时，以备份分支代码的实际行为为准；若历史测试断言与代码行为冲突，测试需要回到实际业务语义。
