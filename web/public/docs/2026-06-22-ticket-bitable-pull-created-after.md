# 2026-06-22 多维表格主动拉取创建时间窗口

## 结论

- 定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 新增创建时间窗口控制。
- 任务未指定时间时，默认只处理当前时间前 1 小时之后创建的飞书多维表格记录。
- 任务指定 `createdAfter`、`created_after`、`startTime`、`start_time`、`beginTime`、`begin_time` 任一参数时，使用指定时间作为创建时间下限。

## 实现说明

1. 定时任务入口提取主动拉取覆盖配置后补齐 `createdAfter`。
2. `TicketSyncService.run_bitable_pull_services` 查询飞书记录后，按记录级 `created_time/createdTime/created_at/createdAt` 做本地过滤。
3. 返回结果新增：
   - `queriedRecordCount`：飞书接口查询到的原始记录数。
   - `recordCount`：创建时间过滤后的处理记录数。
   - `createdAfter`：本次实际使用的创建时间下限。

## 参数示例

```json
{
  "createdAfter": "2026-06-22 10:48:00"
}
```

也可以放在嵌套配置中：

```json
{
  "bitablePull": {
    "createdAfter": "2026-06-22 10:48:00"
  }
}
```

## 风险说明

- 当前过滤使用飞书记录元数据创建时间，不依赖多维表格中的自定义“创建时间”字段。
- 如果飞书接口未返回记录创建时间，该记录会被跳过，并输出跳过日志。
