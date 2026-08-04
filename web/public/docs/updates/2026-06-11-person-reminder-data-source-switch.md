# 2026-06-11 按人催办统计数据源切换（bitable/local）

## 背景

按人催办原实现仅支持飞书多维表格统计。当前需求要求增加一个配置项，可在“多维表格统计”和“本地数据统计”之间切换。

## 本次改动

1. 新增配置字段：
   - `personReminder.dataSource`
   - 可选值：`bitable` / `local`
   - 默认值：`bitable`
1. 后端统计分流：
   - `bitable`：沿用原飞书多维表格统计逻辑；
   - `local`：从本地 `ticket` 表统计，按“当前处理人”聚合超时工单。
1. 本地统计规则：
   - 聚合维度：`current_assignee_id/current_assignee_name`
   - 时间字段：`timeField`（支持 `update_time/create_time/started_at/resolved_at/closed_at`，非法值回退 `update_time`）
   - 超时阈值：`thresholdMinutes`
   - 默认不统计关闭/完成状态（可通过配置 `includeClosed=true` 放开）
1. 配置校验调整：
   - `bitable` 模式继续校验 `appId/appSecret/appToken/tableId/personField/timeField`；
   - `local` 模式不再要求多维表格配置。
1. 前端配置页增强：
   - 新增“统计数据源”下拉；
   - 选择 `bitable` 时展示多维表格专属字段；
   - 选择 `local` 时展示本地时间字段下拉。
1. 日志增强：
   - 按人催办预览与执行日志中增加 `data_source` 输出，方便排查来源链路。

## 影响范围

1. 工单同步配置页 `personReminder` 配置区域。
1. 人员催办统计预览接口：`POST /ticket/sync/notify/person/preview`
1. 人员催办执行接口：`POST /ticket/sync/notify/person/run`
1. 定时任务：`module_task.scheduler_maintenance.ticket_person_overdue_reminder`
