# 多维表格主动拉取强制同步与字段保留修复

## 变更日期

- 2026-06-24

## 结论

- 飞书多维表格主动拉取新增 `forceSync` 参数，开启后会忽略本地 `recordId + snapshotHash` 去重，重新执行入库和延后后处理。
- 主动拉取字段映射会把项目、模块、内部负责人等外部字段写入 `extraData.external_field_mapping`，并同步转换为工单模型可识别的顶层字段。
- 主动拉取的自动翻译开关现在会优先生效：当 `bitablePull.automation.autoTranslate=true` 时，即使全局外部同步开关 `autoTranslateOnSync=false`，本次主动拉取仍会执行翻译。

## 问题现象

- 已拉取过的多维表格记录即使远端需要重新覆盖，也会因为本地快照未变化直接跳过。
- 主动拉取任务入库后，项目、模块、内部负责人为空。
- 主动拉取记录执行完成后没有按“主动拉取自动化”的自动翻译开关进行翻译。

## 根因

- 主动拉取历史只按 `recordId + snapshotHash` 判断是否跳过，没有任务级强制同步开关。
- `ticketVender/ticketModle/internalOwner` 等字段不是 `TicketExternalSyncUpsertModel` 的顶层字段，模型校验后会被丢弃；后续识别阶段主要读取 `raw_payload` 和 `extraData.external_field_mapping`，因此拿不到主动拉取映射结果。
- 外部同步翻译判断在 `external_sync` 场景只读取 `autoTranslateOnSync`，没有优先使用主动拉取写入的 `sync_object.automation.autoTranslate`。

## 关键实现

- `TicketSyncService._default_bitable_pull_config()` 新增 `forceSync=false`。
- `module_task.scheduler_maintenance._build_bitable_pull_config_override()` 支持任务参数 `forceSync/force_sync`。
- `TicketSyncService.run_bitable_pull_services()` 在 `forceSync=true` 时绕过 `_should_skip_bitable_pull_record()`。
- 主动拉取字段映射目标字段新增别名：
  - `projectName/project_name/merchantName/merchant_name` -> `ticketVender`
  - `moduleName/module_name/ticketModel/ticket_model` -> `ticketModle`
  - `internalOwnerName/internal_owner_name` -> `internalOwner`
- `_build_bitable_pull_sync_object()` 会把映射后的字段快照写入 `extraData.external_field_mapping`，并把项目、模块、内部负责人同步到 `projectName/moduleName/internalOwnerName`。
- 外部同步和延后后处理翻译决策都改为：存在 `sync_object.automation` 时优先使用 `automation.autoTranslate`，否则回退全局配置。

## 使用方式

定时任务参数示例：

```json
{
  "bitablePull": {
    "forceSync": true,
    "createdAfter": "2026-06-24 00:00:00"
  }
}
```

说明：

- `forceSync` 只控制是否忽略本地快照去重。
- 是否能查到历史远端数据仍由 `createdAfter`、`filterFormula` 和视图范围决定。
- 若来源多维字段本身为空，项目、模块、内部负责人仍不会被自动补出。

## 验证

- `uv run ruff check modules/ticket/service/ticket_sync_service.py module_task/scheduler_maintenance.py tests/test_ticket_sync_mapping_boundary.py`
- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
- `npm run build:prod`
