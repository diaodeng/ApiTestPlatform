# 工单同步自动化配置说明

## 入口

- 菜单：工单管理 → 工单同步配置
- 路由：`/ticket/sync-automation`

## 页面目标

管理"外部同步入库"后的自动化行为，三类数据源：

- 第三方系统直接调用 `/ticket/sync/external` 推送工单
- 内网系统调用 `/ticket/sync/pending` 拉取外网工单
- 拉取后回写 `/ticket/sync/ack` 的交付状态

手动新增/编辑工单的"创建后拉日志"不在这里配置，走工单新增页。轻量翻译和知识提炼的配置走 **AI 配置中心**。

---

## 一、基础开关

### 1.1 同步基础开关

| 配置项 | 说明 |
|--------|------|
| `autoRunOnSync` | 外部同步入库后是否进入自动化链路 |
| `autoTranslateOnSync` | 第三方直推场景下是否自动翻译工单描述 |
| `defaultPullLimit` | 内网拉取未同步工单时的默认数量 |

### 1.2 发布状态

- 外部推送首先写入 `publish_ready=false`，后台 AI/自动化结束后恢复为可发布。
- `/ticket/sync/pending` 拉取前检查是否有活动 AI 任务；无活动任务时自动恢复 `publish_ready=true`。
- 拉取时写入 `status=pulled` 和租约，30 分钟内不重复返回；超时未回执允许重试。
- `/ticket/sync/ack` 只有 `delivered/success/succeeded` 推进交付版本；`failed` 不阻塞下次拉取。

---

## 二、远端同步连接

| 配置项 | 说明 |
|--------|------|
| `remoteSync.enabled` | 是否允许远端拉取任务执行。**不是启动定时任务的按钮**，只控制任务是否放行。关闭时页面不强制校验 `pullUrl/ackUrl/consumer` 必填 |
| `remoteSync.pullUrl` | 拉取未同步工单的地址 |
| `remoteSync.ackUrl` | 回写交付结果的地址 |
| `remoteSync.consumer` | 消费者标识 |
| `remoteSync.includeClosed` | 拉取时是否包含已关闭工单 |
| `remoteSync.autoTranslateOnPull` | 仅控制内网定时拉取链路是否自动翻译（与第三方直推独立控制） |
| `remoteSync.sourceSystem` | 内网拉取后写入的外部系统标识 |
| `credentialBindingId` | 远端同步的凭证绑定 ID（必填） |

---

## 三、识别规则

用于外部同步时将外部字段映射到系统内部字段：

| 配置项 | 说明 |
|--------|------|
| `projectMappings` | 项目映射规则 |
| `moduleMappings` | 模块映射规则 |
| `vendorMappings` | 商家映射规则 |
| `storeMappings` | 门店映射规则 |
| `statusMappings` | 状态映射规则 |
| `assigneeMappings` | 指派人映射规则 |
| `posPatterns` | POS 编号匹配模式 |
| `scoPatterns` | SCO 匹配模式 |
| `versionPatterns` | 版本号匹配模式 |
| `externalSyncBitable` | 外部推送按 recordId 查询飞书多维表格补充人员信息 |

### 业务码匹配

外部映射支持通过 `project_code` / `module_code` 匹配本地项目/模块，兼容顺序：
1. 先看外部字段 `ticketVender` / `ticketModle` 对应的映射
2. 未命中时通过 `projectCode/moduleCode` 匹配
3. 仍未命中且携带当前环境 ID 时，按 `projectId/moduleId` 兜底

---

## 四、日志拉取默认值

`logPullDefaults` 配置外部同步后自动拉日志的默认参数（已加宽显示）。

---

## 五、自动化关注范围

`ticket.sync.automation.automationScope` 可按系统模块控制同步后的自动化范围：

- 按模块 ID、模块 Code、模块名称关键字配置
- 范围外工单仍入库并更新快照和状态，但不执行标题 AI、翻译、AI 提取、AI 分类、自动拉日志/AI 分析、向量刷新和自动群推送
- 工单统计页默认选择"关注范围"，可切换"全部数据"

---

## 六、通知推送配置

### 6.1 群推送

| 配置项 | 说明 |
|--------|------|
| `groupPush.autoPushCondition` | 自动推送条件表达式，手动发送不受此限制 |

### 6.2 个人催办提醒

- 按飞书多维表格中的人员维度统计未处理工单并发送提醒
- 可手动触发或通过调度任务 `module_task.scheduler_maintenance.ticket_person_overdue_reminder` 定时执行
- 统计数据源可选 `bitable` 或 `local`

### 6.3 汇总统计通知

- 页面支持手动触发或定时任务执行
- 统计数据源可选 `local` 或 `bitable`
- 可选开启 AI 解读生成摘要

### 6.4 自定义统计方案

- 在"自定义统计"页签创建统计方案
- 手动执行可选"仅预览"或"按方案通知"
- 定时执行使用 `module_task.scheduler_maintenance.ticket_custom_statistics_report`

---

## 七、AI 分类统一配置

工单同步配置页提供场景开关 `ticket.sync.automation.aiClassification`：

- 控制外部同步、远端拉取、手动创建场景是否执行分类
- 选择 Provider 编码和提示词编码（Provider 和提示词正文在 AI Provider 管理和 AI 提示词管理维护）
- 配置状态变更后是否触发重新分类

配置项 `ticket.ai.category.classify.provider.code` 和 `ticket.ai.category.classify.prompt.code` 作为当分类配置中 Provider/提示词为空时的兜底。

---

## 八、常见问题

### Q1: remoteSync.enabled 关闭后有什么影响？

任务执行前检查该开关，关闭时任务不会实际拉取。页面不再强制校验 `pullUrl/ackUrl/consumer` 必填，可以单独保存其他配置项。

### Q2: 如何只关闭内网拉取的翻译？

修改 `remoteSync.autoTranslateOnPull`，不要改 `autoTranslateOnSync`（影响第三方直推）。

### Q3: 手动新增工单的自动化怎么配置？

手动新增/编辑的"创建后拉日志"和"自动翻译"在工单新增页配置，非本页范围。

### Q4: 如何配置凭证？

远端同步的 `credentialBindingId` 必填。在统一凭证管理中创建 `http_api_key` 或 `http_header` 凭证，再创建 `ticket_remote_sync` 类型的业务绑定。

---

## 相关文档

- [统一凭证管理](credential_management.md)
- [工单日志查看器使用说明](ticket_log_viewer.md)
