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

| 配置项 | 说明 |
|--------|------|
| `logPullDefaults.environment` | 默认日志环境，格式为 `分组:子环境`；必须来自日志拉取外部接口配置 |
| `logPullDefaults.commandDataType` | 外部日志命令数据类型 |
| `logPullDefaults.storageMode` | 日志归档方式，如 `local` 或 `ftp` |
| `logPullDefaults.autoAiEnabled` | 日志拉取成功后是否自动发起 AI 分析 | `false` |
| `logPullDefaults.aiAgentCode` / `aiProviderCode` | 自动 AI 使用的 Agent / Provider 编码，至少配置一个 | 空字符串 |
| `logPullDefaults.autoAiAnalysisCondition.analysisMode` | 历史分析条件：`always` 每次允许，`not_successful` 仅工单没有成功分析记录时允许 | `always` |
| `logPullDefaults.autoAiAnalysisCondition.statusFilterEnabled` | 是否启用内部工单状态过滤 | `false` |
| `logPullDefaults.autoAiAnalysisCondition.statusCodes` | 允许自动分析的内部状态编码列表，由页面下拉多选生成 | `[]` |

自动 AI 条件只有在“自动 AI 分析”开启时生效，并按 AND 关系检查：自动 AI 已开启、工单状态命中允许列表（启用状态过滤时）、历史分析条件满足、没有正在执行的 AI 任务。状态配置使用系统内部状态编码，不直接填写外部状态文案；外部状态必须先通过“状态映射”转换为内部状态。状态为空、未映射或不在允许列表时，只跳过自动 AI，不影响日志拉取，也不会消耗 Token。

页面入口为“工单同步自动化 → 日志拉取配置 → 拉日志默认值”。启用状态过滤后，在“允许的工单状态”中多选内部工作流状态；保存时至少选择一个状态。手动发起 AI 分析和手动重试不受这些自动分析条件限制。

示例：

```json
{
  "autoAiEnabled": true,
  "autoAiAnalysisCondition": {
    "analysisMode": "not_successful",
    "statusFilterEnabled": true,
    "statusCodes": ["pending", "processing", "wait_dev"]
  }
}
```

其中“默认日志环境”在“工单同步自动化 → 日志拉取配置 → 拉日志默认值”中选择，选项来自“外部接口”已保存的环境分组和子环境，保存格式为 `分组:子环境`，例如 `PROD:PROD`。自动拉日志未在任务级单独指定环境时使用该值；未配置时会记录缺少 `environment` 并跳过提交，避免创建必然失败的后台任务。

---

## 五、自动化关注范围

`ticket.sync.automation.automationScope` 可按系统模块控制同步后的自动化范围：

- 按模块 ID、模块 Code、模块名称关键字配置
- 范围外工单仍入库并更新快照和状态，但不执行标题 AI、翻译、AI 提取、AI 分类、自动拉日志/AI 分析、向量刷新和自动群推送
- 工单统计页默认选择"关注范围"，可切换"全部数据"

---

## 六、自动化结果通知

“同步后自动化”配置卡中的“自动化结果通知”用于接收自动拉日志、日志拉取后的自动 AI 分析结果。启用后选择已有的推送配置服务，并分别控制成功、失败是否发送。未启用、未选择推送配置或关闭对应结果开关时，不会发送消息。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `automationNotification.enabled` | 是否启用自动化结果通知 | `false` |
| `automationNotification.pushIds` | 需要投递的推送配置 ID，可选择多个 | `[]` |
| `automationNotification.success.push` | 日志拉取或 AI 分析成功时是否推送 | `true` |
| `automationNotification.failed.push` | 拉取、创建任务或分析失败/跳过时是否推送 | `true` |
| `automationNotification.messageTemplate` | 消息模板；留空使用系统默认模板 | 空字符串 |

自动化开始时会把当前通知配置快照保存到工单和日志拉取记录中。因此，后续修改配置不会改变已经在运行或已创建的自动化任务的投递渠道和模板。

当自动 AI 在提交阶段被服务拒绝时，通知中的 `${reason}` 会显示服务返回的实际 `result.message`（例如指定 Agent 未连接），不会只显示记录 ID；工单时间线也会记录 `auto-ai:failed` 事件及同一原因，便于定位失败发生在创建 AI 任务之前。

部署注意：`start.sh` 使用 Supervisor 将 FastAPI 与 Celery Worker 分成独立进程。自动 AI 现在会通过 FastAPI 内部网关 `/qtr/agent/ai-analysis/send/{agent_code}` 进行跨进程派发，并按 AI 配置中心中的“Agent 并发数”做排队控制。Agent WebSocket 仍只在 FastAPI 进程内维护，但 Celery Worker 不再直接依赖进程内连接表。

### 6.1 通知模板变量

模板使用 `${变量名}` 格式。模板中未识别的变量会原样保留；格式不合法时系统会回退到默认模板并记录告警日志。

| 变量 | 含义 |
|------|------|
| `${ticket_no}` | 工单号 |
| `${ticket_title}` | 工单标题 |
| `${merchant_name}` | 商家名称 |
| `${store_name}` | 门店名称；没有名称时显示日志拉取门店编号 |
| `${stage}` | 自动化阶段编码，如 `log_pull`、`ai_analysis` |
| `${stage_label}` | 自动化阶段中文名称，如“日志拉取”“AI 分析” |
| `${status}` | 结果状态编码，如 `success`、`failed` |
| `${status_label}` | 结果状态中文名称，如“成功”“失败” |
| `${message}` | 结果简要说明 |
| `${reason}` | 失败原因或结果说明，优先使用详细信息 |
| `${detail}` | 任务 ID、日志记录 ID 或异常详情 |
| `${ticket_url}` | 工单详情链接 |
| `${title}` | 通知标题 |

示例：

```text
【${status_label}】${stage_label}
工单：${ticket_no} ${ticket_title}
商家/门店：${merchant_name} / ${store_name}
原因：${reason}
```

## 七、通知推送配置

### 7.1 群推送

| 配置项 | 说明 |
|--------|------|
| `groupPush.autoPushCondition` | 自动推送条件表达式，手动发送不受此限制 |

### 7.2 个人催办提醒

- 按飞书多维表格中的人员维度统计未处理工单并发送提醒
- 可手动触发或通过调度任务 `module_task.scheduler_maintenance.ticket_person_overdue_reminder` 定时执行
- 统计数据源可选 `bitable` 或 `local`

### 7.3 汇总统计通知

- 页面支持手动触发或定时任务执行
- 统计数据源可选 `local` 或 `bitable`
- 可选开启 AI 解读生成摘要

### 7.4 自定义统计方案

- 在"自定义统计"页签创建统计方案
- 手动执行可选"仅预览"或"按方案通知"
- 定时执行使用 `module_task.scheduler_maintenance.ticket_custom_statistics_report`

---

## 八、AI 分类统一配置

工单同步配置页提供场景开关 `ticket.sync.automation.aiClassification`：

- 控制外部同步、远端拉取、手动创建场景是否执行分类
- 选择 Provider 编码和提示词编码（Provider 和提示词正文在 AI Provider 管理和 AI 提示词管理维护）
- 支持独立选择模型名称，留空则使用 Provider 默认模型
- 配置状态变更后是否触发重新分类

配置项 `ticket.ai.category.classify.provider.code` 和 `ticket.ai.category.classify.prompt.code` 作为当分类配置中 Provider/提示词为空时的兜底。

## 九、AI 配置段通用说明

同步自动化配置中以下 AI 配置段均支持独立选择 Provider 和模型：

| 配置段 | 说明 |
|--------|------|
| `translateConfig` | 工单翻译，支持按场景（外部同步/远端拉取/多维表格拉取/手动创建）开关 |
| `titleSummaryConfig` | 工单标题总结，缺少标题时自动生成 |
| `knowledgeConfig` | 工单知识提炼，从工单上下文生成知识库案例 |
| `aiClassification` | 工单 AI 分类统计 |
| `aiSyncExtract` | 工单同步统一提取，从标题和描述中提取分类、POS/SCO 编号等 |
| `summaryReport` | 汇总通知 AI 解读 |

每个配置段中的 `modelName` 字段均为可选，留空时自动使用对应 Provider 的默认模型。模型的可用列表在 Provider 管理页面的"可用模型"中维护。

---

### 8.1 `aiSyncExtract` 提取规则与提示词建议

`aiSyncExtract` 用于从工单标题、描述和外部原始入参中提取门店编码、POS/SCO 机台编号、日志日期和版本文本。Provider、模型和提示词编码可在 AI 配置中心维护；系统不会限制自定义提示词的表达方式，但会在请求中补充必要的安全约束。

POS/SCO 建议在自定义提示词中明确写成“收银机机台编号”，并要求模型结合字段语义判断，不要对全文数字做简单匹配。推荐加入以下规则：

- `posNo`、`scoNo` 只填写明确属于收银机机台的编号，无法确认时返回 `null`。
- 金额、货币符号、千分位金额、订单号、日期、时间、门店编号和日志行号不能作为 POS/SCO。
- 对“`#2 POS, $44,510.00`”应输出 `posNo=2`；`$44,510.00` 是金额，不能输出 `44`、`44510` 或 `510`。
- 输出 `posNo`、`scoNo` 时使用正整数或 `null`，不要输出带单位、货币符号或解释文字的字符串。
- 当多个数字候选冲突时，优先采用与 POS/SCO 机台语义直接相邻或明确绑定的编号，并在无法确认时留空。

系统还会对模型结果进行安全归一化：金额或千分位文本不会被截取为编号；原文存在明确 POS/SCO 机台语义时，会用该明确值校正模型结果，并把冲突写入 AI 执行审计。同步主路径和延后路径使用同一份回填结果，避免 `ai_sync_extract`、`logPullConfig` 和最终自动拉日志参数出现不同编号。

统一提取会保存业务输入指纹 `sourceHash` 和提示词配置指纹 `promptHash`。相同标题、描述、项目/模块、门店、POS/SCO、日期和版本输入重复同步时直接复用成功结果，不重复消耗 Token；描述、标题、门店或其他上述业务字段变化才重新提取。评论、排查过程、记录链接和同步时间暂不参与提取指纹，因此单纯追加评论不会反复触发提取。已有工单标题只影响标题总结，不会阻止字段提取和分类。

自动拉日志的运行参数以 `extraData.log_pull_hints` 为持久化兜底，并区分外部来源门店编码 `sourceStoreCode` 与日志接口门店 `storeId`。`sourceStoreCode` 只保留外部同步原始值，AI 永远不会反写它。`storeId` 的选择规则如下：

1. 有 `sourceStoreCode` 且 AI 提取值与它相等时，使用 AI 提取值；
2. 有 `sourceStoreCode` 且 AI 提取值包含在来源编码中时，使用 AI 提取值；
3. AI 提取为空或不匹配时，回退使用 `sourceStoreCode`；
4. 没有 `sourceStoreCode` 时，有效 AI 提取值可以替换旧 `storeId`，AI 没有有效值时保留旧值。

因此，同一轮有效 AI 提取到新门店时可以更新 `storeId`，但不会改变 `sourceStoreCode`。如果外部来源值是 SAP 门店编码或其他非 `org_no` 的业务编码，字段识别会先按当前商家门店配置映射为日志接口 `org_no`；自动日志运行参数优先使用这个已映射的 `storeId`，不会再被原始来源编码覆盖。只有最终 `storeId` 会作为日志接口门店参与商家和 `org_no` 校验。若同一商家下同一外部编码匹配到多个不同 `org_no`，系统不会按修改时间或记录顺序静默选择，而是记录全部候选门店并跳过自动日志提交；需要人工确认后再执行。任务级明确参数和当前有效同步字段优先，历史 hints 负责补齐缺失参数；识别审计只记录本次运行，不作为下一次配置来源。

自动拉日志真正提交前，还会按最终运行参数做一次成功记录去重：如果当前工单已经有“相同拉取参数且状态为成功”的日志记录，则这次自动化只记一条“已复用成功日志”的审计，不会重复向外部平台发起相同申请。

日志下载成功后，自动 AI 会优先从已成功日志正文提取版本号并自动创建或复用版本中心记录，正常情况下不需要人工维护 `affectedVersionId`。只有日志正文没有可识别版本，或版本中心关联失败时，才会记录跳过原因。

如果这次同步没有重新拉日志，但工单下已经有最近一次成功日志记录，自动 AI 也会直接复用该成功记录继续执行，不再因为“本轮未新建日志记录”而整体跳过。


### Q1: remoteSync.enabled 关闭后有什么影响？

任务执行前检查该开关，关闭时任务不会实际拉取。页面不再强制校验 `pullUrl/ackUrl/consumer` 必填，可以单独保存其他配置项。

### Q2: 如何只关闭内网拉取的翻译？

修改 `remoteSync.autoTranslateOnPull`，不要改 `autoTranslateOnSync`（影响第三方直推）。

### Q3: 手动新增工单的自动化怎么配置？

手动新增/编辑的"创建后拉日志"和"自动翻译"在工单新增页配置，非本页范围。

### Q4: 如何配置凭证？

远端同步的 `credentialBindingId` 必填。在统一凭证管理中创建 `http_api_key` 或 `http_header` 凭证，再创建 `ticket_remote_sync` 类型的业务绑定。

---

## 十、指定工单手动自动化

当需要补跑某一张工单的同步后自动化，但不希望或不能开启“飞书多维表格主动拉取”定时任务时，可在本页面的 **飞书多维表格主动拉取** 卡片顶部使用“指定工单手动自动化”。该功能不会修改定时任务配置，也不会触发其他工单。

### 10.1 入口与权限

1. 进入 **工单 → 工单同步配置**。
2. 找到 **飞书多维表格主动拉取** 卡片顶部的“指定工单手动自动化”。
3. 输入需要补跑的**精确工单号**，选择数据来源后点击 **执行自动化**。
4. 需要具备 `ticket:sync:config:edit` 权限。

### 10.2 参数说明

| 参数 | 说明 | 默认值 | 可选值与影响 |
|---|---|---|---|
| 工单号 | 需要执行自动化的业务工单号。必须输入精确值。 | 无 | 多维表格模式必须在表格中唯一精确匹配；数据库模式必须存在同工单号的本地工单。 |
| 数据来源 | 决定本次自动化使用哪份数据。 | `查询多维表格` | `查询多维表格`：重新读取飞书记录并按常规多维表格映射同步入库；`使用数据库快照`：读取当前数据库工单，只重放后处理自动化。 |

### 10.3 两种执行模式

#### 查询多维表格

适合希望以飞书多维表格中的最新字段重新模拟一次拉取的场景。

- 本次查询**不受**“启用主动拉取”开关影响；即使定时任务关闭，也可以执行。
- 本次查询忽略常规的 `filterFormula`、`createdAfter`、`createdBefore` 和自动追加时间窗口，只使用输入工单号构造查询条件。
- 仍需要正确配置飞书连接和字段映射：`appId`、`appSecret`、`appToken`、`tableId`、`fieldMappings`。
- 若配置了 `viewId`，飞书视图自身仍可能限制可查询到的记录；找不到记录时请同时检查视图筛选条件。
- 系统会将查询结果转换后再次校验工单号，只允许**一条**精确匹配记录执行。没有匹配记录或出现重复工单号时会拒绝执行，避免误同步相似工单号。
- 匹配成功后会按既有 `bitable_pull` 场景同步该工单，并继续执行后处理自动化。

#### 使用数据库快照

适合飞书记录暂时不可访问、只希望使用已经入库的数据重新触发自动化的场景。

- 系统直接读取数据库中的现有工单 ORM 实体。
- 不会重新调用同步入库，也不会用旧快照覆盖当前工单标题、描述、状态、负责人等字段。
- 会按既有 `bitable_pull` 场景重放后处理自动化，并在工单扩展数据中记录本次手动重放来源和时间，便于排查。

### 10.4 会执行哪些自动化

两种模式都复用现有 `bitable_pull` 场景，因此仍遵循当前同步自动化配置和自动化关注范围。根据已启用的配置，可能执行 AI 字段提取、字段识别、自动拉日志、日志后的自动 AI、自动分类、向量刷新以及通知/群推送等步骤。

手动入口不会绕过以下限制：

- 自动化关注范围不匹配时，AI、日志、向量和自动推送仍会跳过；
- 各子功能的启用开关、Provider、Agent、日志参数和通知配置仍按当前配置校验；
- 外部日志和 AI 等既有异步任务会按原有调度方式继续执行，页面提示“执行完成”表示本次同步与后处理编排已完成，不代表所有后台任务都已产生最终结果。

### 10.5 常见问题

**Q：提示多维表格中找不到工单？** 先确认工单号完全一致，再检查多维表格连接信息、工单号字段映射和 `viewId` 对应视图的筛选范围。手动模式不会使用常规时间窗口和筛选公式。

**Q：提示找到多条相同工单号？** 请先在多维表格中清理或区分重复记录。系统不会任意选择其中一条，以免把错误数据同步到工单。

**Q：为什么执行后没有拉日志或发起 AI？** 该入口仍服从自动化关注范围及自动日志、自动 AI 等开关；请检查工单所属项目/模块是否在范围内，以及日志参数、AI Provider、Agent 等前置条件。

**Q：数据库快照模式为什么没有更新飞书最新字段？** 此模式的设计是不入库、不覆盖工单字段，只利用本地已有数据重放自动化。需要以飞书最新数据为准时，请选择“查询多维表格”。

---

## 相关文档

- [统一凭证管理](credential_management.md)
- [工单日志查看器使用说明](ticket_log_viewer.md)
