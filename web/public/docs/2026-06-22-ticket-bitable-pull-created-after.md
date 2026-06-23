# 2026-06-22 多维表格主动拉取时间窗口

## 结论

- `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 默认使用当前时间前 1 小时作为主动拉取窗口下限。
- 2026-06-24 起，时间窗口下推到飞书 `records/search` 请求参数中的 `filter`，不再先拉取全量记录后本地过滤。
- 默认过滤语义为：更新时间字段或创建时间字段大于等于窗口下限。
- `createdAfter`、`created_after`、`startTime`、`start_time`、`beginTime`、`begin_time` 仍可作为任务参数传入，用于覆盖默认窗口下限。

## 实现说明

1. `TicketSyncService.run_bitable_pull_services` 解析主动拉取运行时配置。
2. 服务在请求飞书前把时间窗口合并进 `filterFormula`。
3. 默认 OR 时间字段：
   - `updatedAtField`，未配置时使用 `更新时间`；
   - 字段映射中 `targetField=createTime` 对应的多维字段，未配置时使用 `创建时间`。
4. 如果现有 `filterFormula` 中上述时间字段的比较条件缺少 `value`，服务会自动填入窗口下限的 13 位毫秒时间戳。
5. 返回结果中的 `queriedRecordCount` 是飞书按 filter 返回后的数量，不再代表全量表扫描数量。

## 参数示例

```json
{
  "createdAfter": "2026-06-24 00:59:00"
}
```

也可以放在嵌套配置中：

```json
{
  "bitablePull": {
    "createdAfter": "2026-06-24 00:59:00"
  }
}
```

## 说明

- `createdAfter` 仍保留为兼容入参，作用是覆盖默认时间窗口下限；它不再代表本地过滤步骤。
- 若需要自定义字段名，优先配置 `updatedAtField` 和字段映射中的 `targetField=createTime`。
- 日期/时间字段过滤值使用 13 位毫秒时间戳传给飞书。
