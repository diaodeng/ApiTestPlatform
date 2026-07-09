# 2026-07-10 工单统计第三阶段：快照口径与周报稳定实现

## 结论

第三阶段已补齐“实时口径 / 快照口径”双路径：

1. `ticket_statistics_daily` 扩展为自然日快照表，新增提交、响应、处理、处理率和未处理存量等字段。
2. 新增每日快照任务 `module_task.scheduler_maintenance.ticket_daily_statistics_snapshot`。
3. 统计页增加统计口径切换，默认实时口径，切到快照口径时读取日快照。
4. 汇总通知配置默认使用快照口径。

## 本次变更范围

- 后端数据模型
- 后端统计服务
- 定时任务
- 统计页
- 文档和 wiki

## 数据模型

### `ticket_statistics_daily`

新增字段：

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

- 当前快照按自然日冻结。
- 快照口径优先服务周报、汇总通知和统计页展示。
- 实时口径仍保留现有统计计算逻辑。

## 接口变化

### `GET /ticket/statistics/overview`

新增参数：

- `statisticsMode=realtime`
- `statisticsMode=snapshot`

### `GET /ticket/statistics/trend`

同样支持 `statisticsMode`。

## 前端变化

- 统计页增加“实时口径 / 快照口径”切换。
- 快照模式下增加提示，说明当前读取的是冻结快照。

## 调度任务

### `module_task.scheduler_maintenance.ticket_daily_statistics_snapshot`

职责：

- 按自然日生成工单统计快照
- 写入 `ticket_statistics_daily`

## 已知限制

1. 当前快照表仍是自然日整体快照，不包含项目、模块等维度拆分。
2. 快照口径下项目/模块/问题类型筛选暂不参与快照聚合。
3. 若后续需要“按项目/模块冻结快照”，需要进一步扩展快照表维度。

## 验证

- 已执行 `ruff check`
- 前端构建执行过一次，超时，未获得最终成功结果
- `pytest` 在当前环境不可用
