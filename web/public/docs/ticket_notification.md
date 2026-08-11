# 工单通知功能使用说明

## 入口

- 菜单：工单管理 → 工单同步配置
- 路由：`/ticket/sync-automation`
- 页面内切到"通知"相关配置区域（群推送 / 按人催办 / 汇总统计 / 自定义统计）

## 功能概览

工单通知体系包含四类通知能力：

| 通知类型 | 说明 | 触发方式 |
|----------|------|----------|
| 群消息推送 | 新工单入库后自动推送到指定飞书群 | 自动（入库触发）/ 手动 |
| 按人催办提醒 | 按处理人维度统计超时工单并发送提醒 | 手动 / 定时任务 |
| 汇总统计通知 | 定期统计工单数据并通过飞书/AI推送 | 手动 / 定时任务 |
| 自定义统计方案 | 定义定制化统计维度并定时通知 | 手动（预览/发送）/ 定时任务 |

---

## 一、群消息推送

### 1.1 功能说明

工单通过外部同步、远端拉取、多维表格拉取或手动创建入库后，可按配置自动发送群消息到指定飞书群聊，让团队第一时间知晓新工单。

### 1.2 配置项

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `groupPush.enabled` | 开关 | 是否启用群推送 |
| `groupPush.sendMode` | 下拉 | 发送模式：`push_config`（推送渠道）、`feishu_app`（飞书应用）、`hybrid`（混合） |
| `groupPush.pushIds` | 多选 | 推送渠道 ID 列表 |
| `groupPush.appChatIds` | 多选 | 飞书群聊 ID 列表（飞书应用模式） |
| `groupPush.sendAfterExternalSync` | 开关 | 外部同步入库后是否自动推送 |
| `groupPush.sendAfterRemotePull` | 开关 | 远端拉取入库后是否自动推送 |
| `groupPush.sendAfterBitablePull` | 开关 | 多维表格拉取入库后是否自动推送 |
| `groupPush.sendAfterManualCreate` | 开关 | 手动创建工单后是否自动推送 |
| `groupPush.autoPushCondition` | 表达式 | 自动推送条件表达式（Python 语法），仅满足条件的工单才自动推送。手动发送不受此限制 |
| `groupPush.priorityRoutes` | 列表 | 优先级路由规则，按顺序匹配工单字段决定推送目标群 |
| `groupPush.template` | 文本 | 群消息模板（自动推送） |
| `groupPush.manualTemplate` | 文本 | 群消息模板（手动推送） |

### 1.3 条件表达式

`autoPushCondition` 支持 Python 表达式，可用的工单字段包括：

- `status`、`statusName`：工单状态
- `priority`、`priorityName`：优先级
- `projectId`、`moduleId`：项目和模块ID
- `ticketVender`：商家/供应商
- `issueTypeId`：问题分类

示例：
```python
statusName == "处理中" and priorityName in ("高", "紧急")
```

### 1.4 手动推送

在工单详情页或列表页可手动触发群推送，支持：
- 选择指定工单号发送
- 设置是否强制推送（忽略已推送状态）
- 手工推送始终不受 `autoPushCondition` 限制

### 1.5 去重机制

- 每张工单在自动推送场景下只推送一次（`groupPushSentOnce` 标记）
- 手动强制推送可绕过此限制
- 推送结果中的飞书消息引用会被持久化，便于后续追溯

---

## 二、按人催办提醒

### 2.1 功能说明

按处理人维度统计超出指定时间阈值仍未处理的工单，并向对应处理人发送催办提醒消息。数据源可选择飞书多维表格或本地数据库。

### 2.2 配置项

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `personReminder.enabled` | 开关 | 是否启用按人催办 |
| `personReminder.sendMode` | 下拉 | 发送模式：`push_config` / `feishu_app` / `hybrid` |
| `personReminder.dataSource` | 下拉 | 数据来源：`bitable`（飞书多维表格）/ `local`（本地数据库） |
| `personReminder.pushIds` | 多选 | 催办推送渠道 ID 列表 |
| `personReminder.appId` | 文本 | 飞书应用 ID（飞书应用模式） |
| `personReminder.appSecret` | 文本 | 飞书应用密钥 |
| `personReminder.thresholdMinutes` | 数字 | 超时阈值（分钟），超过此时间的工单纳入催办范围 |
| `personReminder.maxRowsPerPerson` | 数字 | 每人最多展示的工单行数 |

**多维表格模式额外配置：**

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `personReminder.appToken` | 文本 | 飞书多维表格应用 Token |
| `personReminder.tableId` | 文本 | 多维表格表 ID |
| `personReminder.viewId` | 文本 | 多维表格视图 ID |
| `personReminder.personField` | 文本 | 人员字段名（默认"当前处理人"） |
| `personReminder.timeField` | 文本 | 时间字段名（默认"创建时间"） |
| `personReminder.pageSize` | 数字 | 每页拉取条数 |
| `personReminder.filterFormula` | 文本 | 飞书多维表格过滤公式 |

### 2.3 消息模板

催办消息模板支持变量替换：

| 变量 | 说明 |
|------|------|
| `${person_name}` | 处理人姓名 |
| `${threshold_minutes}` | 超时阈值（分钟） |
| `${overdue_count}` | 超时工单数 |
| `${now_time}` | 统计时间 |
| `${rows_markdown}` | 工单行列表（Markdown 格式） |

行模板变量：`${index}`（序号）、`${created_at}`、`${detail_link}`

### 2.4 手动执行

在工单同步配置页底部"通知手动触发"区域：

- **预览催办**：统计当前超时情况但不发送
- **发送该用户催办**：指定用户或邮箱立即发送催办
- 支持指定用户的 `user_id` 或 `email`

### 2.5 定时任务

- 任务 key：`module_task.scheduler_maintenance.ticket_person_overdue_reminder`
- 可在系统监控 → 定时任务中配置执行周期
- 定时任务可传入 `personConfigOverride` 覆盖全局配置的特定字段

---

## 三、汇总统计通知

### 3.1 功能说明

定期汇总工单数据（数量、状态分布、分类分布、优先级分布），支持 AI 解读，通过飞书消息推送到指定群聊或个人。

### 3.2 配置项

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `summaryReport.enabled` | 开关 | 是否启用汇总通知 |
| `summaryReport.sendMode` | 下拉 | 发送模式：`push_config` / `feishu_app` / `hybrid` |
| `summaryReport.dataSource` | 下拉 | 数据来源：`bitable` / `local` |
| `summaryReport.pushIds` | 多选 | 推送渠道 ID 列表 |
| `summaryReport.appChatIds` | 多选 | 飞书群聊 ID 列表 |
| `summaryReport.statisticsMode` | 下拉 | 统计模式：`snapshot`（快照）/ `incremental`（增量） |
| `summaryReport.windowMinutes` | 数字 | 统计时间窗口（分钟），默认 60 |
| `summaryReport.endDelayMinutes` | 数字 | 结束时间延迟（分钟），默认 0 |
| `summaryReport.includeClosed` | 开关 | 是否包含已关闭工单 |
| `summaryReport.startTime` | 文本 | 手动指定统计开始时间 |
| `summaryReport.endTime` | 文本 | 手动指定统计结束时间 |

**多维表格模式额外配置：**与按人催办的 bitable 字段类似（`appToken`、`tableId`、`viewId` 等）。

**本地模式额外配置：**

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `summaryReport.timeField` | 下拉 | 统计时间字段：`submit_time` / `create_time` |

**AI 解读配置：**

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `summaryReport.aiEnabled` | 开关 | 是否启用 AI 解读 |
| `summaryReport.aiProviderCode` | 下拉 | AI Provider 编码（需先在 AI Provider 管理中配置） |
| `summaryReport.aiPromptCode` | 下拉 | AI 提示词编码（需先在 AI 提示词管理中配置） |

### 3.3 消息模板

汇总模板支持 `${start_time}`、`${end_time}`、`${total_count}`、`${status_summary}`、`${category_summary}`、`${priority_summary}`、`${ai_summary}`、`${now_time}`、`${time_field}` 等变量。

### 3.4 手动执行

在工单同步配置页底部"汇总统计手动触发"区域点击"发送汇总统计"按钮。

### 3.5 定时任务

- 任务 key：`module_task.scheduler_maintenance.ticket_summary_report`
- 在系统监控 → 定时任务中配置

---

## 四、自定义统计方案

### 4.1 功能说明

在"自定义统计"页签中创建定制化统计方案，自定义统计维度、筛选条件和通知方式，支持手动预览/发送和定时任务执行。

### 4.2 配置项

| 配置项 | 说明 |
|--------|------|
| 方案名称 | 自定义方案标识 |
| 启用 | 是否启用该方案（定时任务只执行已启用方案） |
| 统计字段 | 多选：问题分类、状态、来源、根因分类、解决方案、优先级等 |
| 筛选条件 | 项目、模块、状态、时间范围等 |
| 通知 | 开启/关闭通知、发送模式、推送渠道、飞书群聊 ID |
| 消息模板 | 自定义消息模板 |

### 4.3 手动执行

- **仅预览**：查看统计结果但不发送通知
- **按方案通知**：执行统计并通过方案配置的渠道发送通知

### 4.4 定时任务

- 任务 key：`module_task.scheduler_maintenance.ticket_custom_statistics_report`
- 按调度参数执行指定方案或全部已启用方案

---

## 五、飞书多维表格配置

### 5.1 作用

飞书多维表格在通知体系中扮演两个角色：

1. **数据源**：按人催办和汇总统计可以选择从多维表格读取工单数据（`dataSource: bitable`）
2. **用户信息补全**：群推送时从多维表格获取用户的飞书 OpenID、邮箱等信息

### 5.2 配置

| 配置项 | 说明 |
|--------|------|
| `externalSyncBitable.appId` | 飞书应用 ID |
| `externalSyncBitable.appSecret` | 飞书应用密钥 |
| `externalSyncBitable.appToken` | 多维表格应用 Token |
| `externalSyncBitable.tableId` | 默认表 ID |
| `externalSyncBitable.viewId` | 默认视图 ID |
| `externalSyncBitable.personField` | 人员字段名 |
| `externalSyncBitable.nameField` | 姓名字段名 |
| `externalSyncBitable.emailField` | 邮箱字段名 |
| `externalSyncBitable.pageSize` | 每页拉取条数 |

> 此配置供汇总、催办、邮箱补全、主动拉取默认继承使用。

---

## 六、常见问题

### Q1: 群推送和催办有什么区别？

- 群推送：工单入库时向群聊发送通知，关注"有新工单来了"
- 催办提醒：定期检查超时未处理的工单，向处理人个人发送提醒，关注"你的工单该处理了"

### Q2: 如何只启用催办不启用群推送？

分别设置 `personReminder.enabled = true` 和 `groupPush.enabled = false`。

### Q3: 多维表格模式和本地模式如何选择？

- 工单数据存储在飞书多维表格时选择 `bitable`
- 工单数据存储在本系统数据库时选择 `local`
- 两者数据源相互独立，不会重复统计

### Q4: 自定义统计方案和汇总统计有什么区别？

- 汇总统计：固定字段的通用统计（状态/分类/优先级），适合日常汇报
- 自定义统计：自定义维度组合的专项统计，适合特定分析需求

### Q5: 定时任务如何配置？

在系统监控 → 定时任务中新建或编辑任务，填入对应的 task key（如 `ticket_person_overdue_reminder`），设置 cron 表达式和参数。

---

## 相关文档

- [工单同步自动化配置说明](ticket-sync-automation.md)
- [AI Provider 管理说明](ai_provider_management.md)
- [工单日志查看器使用说明](ticket_log_viewer.md)
