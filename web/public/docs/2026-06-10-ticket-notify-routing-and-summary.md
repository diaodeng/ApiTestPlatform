# 2026-06-10 工单通知增强：优先级分流 + 汇总统计 + 统一飞书凭证

## 背景

本次改造基于“工单通知相关”需求，目标是把通知链路补齐到可直接用于生产调度：

1. 同步入库后按工单优先级分流发群；
2. 支持按人催办（可走机器人或飞书应用私信邮箱）；
3. 新增定时汇总统计（状态/分类/优先级）推送；
4. `app_id/app_secret` 统一配置，且允许在子配置中覆盖；
5. 页面可视化配置与日志信息可追踪。

## 核心改动

## 1. 同步配置结构扩展

`ticket.sync.automation` 新增/扩展如下字段：

- `feishuAuth`
  - `appId` / `appSecret`：统一飞书应用凭证。
- `groupPush`
  - `sendMode`：`push_config` / `feishu_app` / `hybrid`。
  - `appChatIds`：应用身份发群目标。
  - `priorityRoutes`：优先级路由（支持 `P1`、`P2`、`P3/P4` 等组合）。
- `personReminder`
  - `sendMode`：`push_config` / `feishu_app` / `hybrid`。
  - `appId` / `appSecret`：可覆盖统一凭证（未填时继承 `feishuAuth`）。
  - 兼容旧字段 `feishuAppId` / `feishuAppSecret`。
- `summaryReport`
  - `enabled`、`sendMode`、`pushIds`、`appChatIds`。
  - `timeField`、`windowMinutes`、`endDelayMinutes`、`startTime`、`endTime`。
  - `includeClosed`、`messageTemplate`。

## 2. 群推送能力增强

- 按工单优先级命中 `priorityRoutes`，优先使用路由目标；
- 未命中时回退 `groupPush.pushIds/appChatIds`；
- `hybrid` 模式下支持自动降级（任一路径缺失时使用另一条可用路径）；
- 触发场景仍支持：
  - 外部同步后自动推送；
  - 远端拉取后自动推送；
  - 手动按工单号发送。

## 3. 按人催办增强

- 催办发送支持三种模式：
  - `push_config`：沿用推送配置；
  - `feishu_app`：按邮箱私发消息；
  - `hybrid`：两种都发（缺一路时降级）。
- 人员统计逻辑保持：
  - 飞书多维表格拉取；
  - 按人员字段聚合；
  - 按阈值过滤超时记录；
  - 生成按人摘要发送。

## 4. 新增汇总统计通知

- 新增汇总执行逻辑：按时间范围统计工单数量，并输出：
  - 状态统计；
  - 分类统计；
  - 优先级统计。
- 支持发送模式：
  - `push_config` / `feishu_app` / `hybrid`。
- 新增手动接口：
  - `POST /ticket/sync/notify/summary/run`
- 新增定时任务键：
  - `module_task.scheduler_maintenance.ticket_summary_report`

## 5. 可视化配置增强

页面 `工单管理 -> 工单同步配置` 新增：

- 飞书统一凭证卡片；
- 群推送发送模式、应用群 chat_id、优先级路由；
- 按人催办发送模式与应用凭证覆盖；
- 汇总统计配置与手动触发入口。

## 使用建议

1. 先在“飞书统一凭证”配置 `appId/appSecret`，再配置各通知模块；
2. 群推送若要求 P1/P2/P3-P4 分流，优先配置 `priorityRoutes`；
3. 汇总统计建议先手动触发确认模板，再挂定时任务；
4. `hybrid` 模式可用于平滑迁移（机器人到应用身份）。

