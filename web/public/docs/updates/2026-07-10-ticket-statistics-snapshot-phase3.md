# 2026-07-10 工单统计第三阶段：快照口径与周报稳定实现

## 结论

第三阶段已补齐“实时口径 / 快照口径”双路径：

1. `ticket_statistics_daily` 扩展为自然日快照表，新增提交、响应、处理、处理率和未处理存量等字段。
2. 快照进一步补齐项目、模块、模块 Code、工单类型维度，支持统计页按这些维度读取冻结口径。
3. 新增每日快照任务 `module_task.scheduler_maintenance.ticket_daily_statistics_snapshot`。
4. 统计页增加统计口径切换，默认实时口径，切到快照口径时读取日快照。
5. 汇总通知配置默认使用快照口径。

## 本次变更范围

- 后端数据模型
- 后端统计服务
- 定时任务
- 统计页
- 文档和 wiki

## 数据模型

### `ticket_statistics_daily`

新增字段：

- `snapshot_scope`
- `project_id`
- `project_name`
- `module_id`
- `module_name`
- `module_code`
- `issue_type_id`
- `issue_type_name`
- `total_count`
- `submitted_count`
- `first_responded_count`
- `processed_count`
- `processed_in_new_count`
- `process_rate`
- `resolved_count`
- `closed_count`
- `unprocessed_backlog`
- `open_backlog`
- `avg_first_response_seconds`
- `avg_first_process_seconds`
- `avg_resolve_seconds`
- `avg_close_seconds`

### 说明

- `snapshot_scope=all` 表示自然日全局快照。
- `snapshot_scope=leaf` 表示按 `project_id + module_id + issue_type_id` 冻结的叶子维度快照。
- 快照按自然日冻结；周/月趋势读取日快照后再按趋势粒度聚合。
- 快照口径优先服务周报、汇总通知和统计页展示。
- 实时口径仍保留现有统计计算逻辑。
- 多维度合并时，平均耗时按事件数量加权，存量指标取周期最后一天的维度存量后求和。

### 迁移脚本

- 第一段扩展自然日指标：`server/sql/20260710_ticket_statistics_snapshot_phase3.sql`
- 第二段补齐维度字段和索引：`server/sql/20260710_ticket_statistics_dimensional_snapshot.sql`

执行第二段脚本后，需要重跑目标日期的快照任务，历史日期不会自动补齐叶子维度行。

## 接口变化

### `GET /ticket/statistics/overview`

新增参数：

- `statisticsMode=realtime`
- `statisticsMode=snapshot`
- `issueTypeIds=bug,support_consulting`

### `GET /ticket/statistics/trend`

同样支持 `statisticsMode` 和 `issueTypeIds`。

### 快照筛选范围

快照口径支持以下筛选：

- `projectIds`
- `moduleIds`
- `moduleCodes`
- `issueTypeIds`

快照口径暂不支持 `problemPatternCodes`。细分问题类型仍只在实时口径中参与过滤。

## 前端变化

- 统计页增加“实时口径 / 快照口径”切换。
- 统计页新增“工单类型”筛选。
- 快照模式下提示项目、模块、模块 Code 和工单类型筛选会参与快照聚合，细分问题筛选只对实时口径生效。

## 调度任务

### `module_task.scheduler_maintenance.ticket_daily_statistics_snapshot`

职责：

- 按自然日生成工单统计快照
- 写入 `ticket_statistics_daily`
- 同一天会生成 1 条全局快照和多条叶子维度快照

## 已知限制

1. 快照口径当前按工单类型 `issue_type_id` 冻结，不按细分问题类型 `problem_pattern_code` 冻结。
2. 历史日期的维度快照需要按日期重跑任务补齐。
3. 快照统计块只展示已冻结的模块和工单类型分布，其他分类块不从实时表临时拼接，避免冻结口径和实时口径混用。

## 验证

- 已执行 `uv run python -m py_compile ...` 检查相关后端文件语法。
- 待执行 `uv run ruff check .`。
- 待执行 `uv run pytest tests/test_ticket_processing_metrics.py`。
- 待执行 `npm run build:prod`。
