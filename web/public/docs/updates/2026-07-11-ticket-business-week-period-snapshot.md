# 2026-07-11 工单业务周周期快照实现记录

## 结论

本次新增业务周周期快照表和业务周快照任务，`statisticsMode=snapshot && granularity=week && weekBucketMode=business_week` 不再返回自然日限制提示，而是读取业务周周期快照做精确统计。

## 后端变更

1. 新增模型 `TicketStatisticsPeriodSnapshot`，对应表 `ticket_statistics_period_snapshot`。
2. 新增 DAO `TicketStatisticsPeriodSnapshotDao`，只负责周期快照查询和 upsert。
3. 新增迁移脚本 `server/sql/20260711_ticket_statistics_period_snapshot.sql`。
4. `TicketStatisticsSnapshotService.build_business_week_snapshot()` 生成上一完整业务周或指定业务周快照。
5. 新增定时任务 `module_task.scheduler_maintenance.ticket_business_week_statistics_snapshot`。
6. `TicketProcessingStatsService` 在快照口径业务周下读取周期快照，overview 和 trend 保持同一口径。
7. `/ticket/statistics/overview` 传递 `weekBucketMode`，`/ticket/statistics/time-config` 返回 `snapshotBusinessWeekSupported=true`。

## 统计口径

- 业务周开始时间来自系统参数 `ticket.statistics.time.config.businessWeekStartTime`，默认周四 18:00。
- 业务周快照写入全局行和 `项目 + 模块 + 工单类型` 叶子维度行。
- 快照趋势桶标签为 `YYYY-MM-DD业务周`，日期为业务周开始日期。
- 自然日、自然周和自然月快照仍读取 `ticket_statistics_daily`。
- 细分问题类型仍未冻结到快照表，快照口径下不参与筛选。

## 手动补跑

默认统计上一完整业务周：

```json
{}
```

补跑单个业务周：

```json
{
  "period_start_time": "2026-07-09 18:00:00"
}
```

范围补跑：

```json
{
  "begin_time": "2026-06-25 18:00:00",
  "end_time": "2026-07-09 18:00:00"
}
```

## 验证

- `cd server && uv run ruff check modules/ticket tests/test_ticket_processing_metrics.py module_task/scheduler_maintenance.py`
- `cd server && uv run --with pytest python -m pytest tests/test_ticket_processing_metrics.py tests/test_ticket_statistics_time_util.py`
