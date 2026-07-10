# 工单每日快照任务增强

**日期**：2026-07-10

**类型**：功能增强

## 背景

`ticket_daily_statistics_snapshot` 定时任务原先默认统计"今天"的数据，且只支持单日模式（`statistics_date`），不支持日期范围批量补跑。统计"今天"在 23:55 执行时会丢失 23:55~24:00 之间的数据。

## 改动内容

### 1. 任务函数参数改造

**文件**：`server/module_task/scheduler_maintenance.py`

新增 `begin_date` 和 `end_date` 参数，支持三种调用模式：

| 模式 | 参数 | 行为 |
|------|------|------|
| 默认 | 不传参 | 统计昨天 |
| 单日 | `statistics_date` | 统计指定单天 |
| 范围 | `begin_date` + `end_date` | 逐日循环统计范围 |

#### 默认模式改为"昨天"

原来默认统计"今天"，改为默认统计"昨天"（`date.today() - timedelta(days=1)`），确保统计完整自然日数据。

#### 范围模式

- 逐日循环 `begin_date` 到 `end_date`（含），每天独立创建数据库会话和 commit
- 某天失败不影响其他天，失败日期记录在 `failed_days` 列表中
- 支持任务终止标记检查，可中途停止
- 返回汇总：`total_days`、`total_leaf_count`、`failed_days`

### 2. 代码拆分

将任务函数拆分为三个职责清晰的方法：

- `ticket_daily_statistics_snapshot()`：入口函数，参数解析和模式路由
- `_run_snapshot_single(date_str)`：单日执行
- `_run_snapshot_range(task_id, begin_date, end_date)`：范围执行

### 3. 导入变更

- 新增 `date` 和 `timedelta` 导入
- 移除不再使用的 `datetime` 导入

### 4. 文档更新

**文件**：`web/public/docs/2026-07-10-ticket-statistics-usage-guide.md`

更新章节：
- 5.1 任务说明：默认统计改为昨天，新增调度时间建议
- 5.3 手动触发快照：三种调用模式说明和示例
- 5.4 快照幂等性：补充 upsert 幂等说明
- 5.5 调度时间建议：新增章节，说明 23:55 和 00:05 的执行策略
- Q3/Q8 FAQ：补充批量补跑建议

## 影响范围

- 定时任务 `ticket_daily_statistics_snapshot` 的参数格式变化（向后兼容，原有 `statistics_date` 参数仍然有效）
- 默认行为变化：从统计"今天"改为统计"昨天"

## 验证结果

- `ruff check` 语法检查通过
- 导入验证通过（`from module_task.scheduler_maintenance import ticket_daily_statistics_snapshot`）

## 调度建议

- 推荐每天 23:55 执行，参数留空（默认统计昨天）
- 或每天 00:05 执行，效果一致

## 无需拆分任务

`TicketStatisticsSnapshotService.build_daily_snapshot()` 已在单次调用中同时生成：
- 1 条全局快照（`snapshot_scope=all`）
- N 条叶子维度快照（`snapshot_scope=leaf`，按 `项目+模块+工单类型` 分组）

只需 1 个定时任务即可。
