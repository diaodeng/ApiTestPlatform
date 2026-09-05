# 工单同步自动化配置说明

## 入口

- 菜单：工单管理 → 工单同步配置
- 路由：`/ticket/sync-automation`

## 页面目标

管理"外部同步入库"后的自动化行为与工单来源链路，三类数据源：

- 第三方系统直接调用 `/ticket/sync/external` 推送工单
- 内网系统调用 `/ticket/sync/pending` 拉取外网工单
- 拉取后回写 `/ticket/sync/ack` 的交付状态

手动新增/编辑工单的"创建后拉日志"不在这里配置，走工单新增页。轻量翻译和知识提炼的配置走 **AI 配置中心**。

## 页面结构（按职责分 6 个页签）

| 页签 | 内容 | 归组依据 |
|------|------|----------|
| 入库流程 | ⓪自动化关注范围、场景×步骤开关总表、①字段识别与映射（弹窗设置）、②外部工单字段模型、③AI 提取、④标题总结、⑤翻译、⑥AI 分类、⑦同步后自动化（含日志拉取设置弹窗入口）、⑧群推送、旁路·知识提炼、提示词模板 | 工单入库后按执行顺序串起来的主链路 |
| 来源与拉取 | 飞书统一凭证、多维表格公共配置、连接解析预览、远端同步链接、飞书多维表格主动拉取、外部推送多维表格邮箱补全 | 工单数据从哪里来 |
| 评论同步 | 工单评论多端同步 | 独立旁路 |
| 通知任务 | 工单汇总统计通知、按人催办通知 | 独立定时任务，非入库链路 |
| 统计与分类 | 统计枚举配置、外部字段工单类型映射、自定义趋势指标、当前系统工单统计方案 | 统计口径 |
| 操作 | 手动触发入口、指定工单手动自动化、自动分类管理 | 手动执行 |

所有页签共用页面底部同一个"保存配置"按钮。两处内容较多的配置收在弹窗中维护：

- **① 字段识别与映射**：页面卡片默认只显示摘要（正则规则组数、映射组数），点击卡片右上角「设置」打开弹窗维护 6 组映射 JSON 与 POS/SCO/版本号正则；修改跟随页面底部「保存配置」一起生效。
- **⑦ 日志拉取设置**：点击"⑦ 同步后自动化"卡片右上角「日志拉取设置」打开弹窗，内含三块配置——拉日志默认值（跟随页面底部「保存配置」保存）、存储与资源限制（弹窗底部独立保存按钮立即生效）、日志拉取外部接口配置（独立保存按钮立即生效）。弹窗顶部有保存方式说明。

---

## 〇、入库流程执行顺序（页面即按此组织）

工单入库（`POST /ticket/sync/external` 或主动拉取/远端拉取复用入库）后，后台按以下顺序执行；页面"入库流程"页签的卡片编号就是执行顺序：

| 步骤 | 内容 | 读取的配置 |
|------|------|------------|
| ⓪ | 自动化关注范围判定（总闸门） | `automationScope` |
| ① | 字段识别与映射（项目/模块/商家/门店/人员/正则），识别失败不阻断 | 识别规则、映射配置 |
| ② | 外部工单字段模型（必填校验与字段全集来源） | `externalFieldModel` |
| ③ | AI 同步提取（回填门店/POS/SCO/日期/版本） | `aiSyncExtract` |
| ④ | 标题总结（仅在缺标题时执行） | `titleSummaryConfig` |
| ⑤ | 翻译（已有成功翻译时跳过） | `translateConfig` |
| ⑥ | AI 自动分类 | `aiClassification` |
| ⑦ | 同步后自动化：自动识别回写 → 自动拉日志 → 自动 AI 分析 | `automationConfig` + `logPullDefaults` |
| ⑧ | 发布状态收敛 + 自动群推送 | `groupPush` |

步骤 ③④⑤⑥⑦⑧ 都受 ⓪ 总闸门约束：范围外工单只执行同步与映射。

该执行顺序对四种入库场景统一生效：外部推送、远端拉取、多维表格拉取和手动创建（页面手工新增工单）。各场景是否执行某一步骤由"场景 × 步骤 开关总表"决定。

---

## 一、场景 × 步骤 开关总表（入库流程页签）

所有"哪个场景执行哪一步"的开关都集中在这一张表里，避免同一开关散落在多个卡片。**每个开关只在这一处出现**；下方各步骤卡片只维护参数（Provider、模型、提示词、模板等）。

| 步骤 ↓ / 场景 → | 外部推送 | 远端拉取 | 多维表格拉取 | 手动创建 | 对应配置键 |
|----------------|---------|---------|-------------|---------|-----------|
| ③ AI 同步提取 | `externalPushEnabled` | `remotePullEnabled` | `bitablePullEnabled` | `manualCreateEnabled` | `aiSyncExtract.*` |
| ⑤ 翻译（含总开关） | `translateOnExternalSync` | `translateOnRemotePull` | `translateOnBitablePull` | `translateOnManualCreate` | `translateConfig.*`，总开关 `enabled` |
| ⑥ AI 自动分类（含总开关） | `runOnExternalSync` | `runOnRemotePull` | `runOnBitablePull` | `runOnManualCreate` | `aiClassification.*`，总开关 `enabled` |
| ⑦ 自动识别 | `autoIdentifyOnExternalSync` | `autoIdentifyOnRemotePull` | `autoIdentifyOnBitablePull` | `autoIdentifyOnManualCreate` | `automationConfig.*` |
| ⑦ 自动拉日志 | `autoLogPullOnExternalSync` | `autoLogPullOnRemotePull` | `autoLogPullOnBitablePull` | `autoLogPullOnManualCreate` | `automationConfig.*` |
| ⑦ 自动 AI 分析 | `autoAiAnalysisOnExternalSync` | `autoAiAnalysisOnRemotePull` | `autoAiAnalysisOnBitablePull` | `autoAiAnalysisOnManualCreate` | `automationConfig.*` |
| ⑧ 自动群推送（含总开关） | `sendAfterExternalSync` | `sendAfterRemotePull` | `sendAfterBitablePull` | `sendAfterManualCreate` | `groupPush.*`，总开关 `enabled` |

说明：

- 场景含义：**外部推送**=第三方系统直推；**远端拉取**=内网定时拉取公网工单；**多维表格拉取**=飞书多维表格定时拉取；**手动创建**=页面手工新增工单。
- 翻译、AI 分类、群推送三行带"总开关"，总开关关闭时该行所有场景开关置灰且不生效；AI 提取和自动识别/拉日志/AI 分析没有总开关，场景开关独立生效。
- 定时任务参数中指定的 automation 配置优先于本表（页面有提示）。
- 状态变更触发的 AI 重归类（`runOnStatusChange`、`statusChangeForceReclassify`、`statusChangeTriggerStatuses`）不属于入库场景，仍在"⑥ AI 分类统计配置"卡片内维护。

## 一点一、自动化关注范围（总闸门）

`automationScope` 可按系统模块控制同步后的自动化范围：

- 按模块 ID、模块 Code、模块名称关键字配置，任一命中即进入范围
- 范围外工单仍入库并更新快照和状态，但不执行 AI 提取、标题 AI、翻译、AI 分类、自动拉日志/AI 分析、向量刷新和自动群推送
- 工单统计页默认选择"关注范围"，可切换"全部数据"

---

## 二、字段识别与映射（入库流程页签 ①）

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

### 业务码匹配

外部映射支持通过 `project_code` / `module_code` 匹配本地项目/模块，兼容顺序：
1. 先看外部字段 `ticketVender` / `ticketModle` 对应的映射
2. 未命中时通过 `projectCode/moduleCode` 匹配
3. 仍未命中且携带当前环境 ID 时，按 `projectId/moduleId` 兜底

### 关键字匹配语义

`projectMappings` / `moduleMappings` 的关键字（`keywords` / `aliases` / `matchText`）在匹配时统一忽略大小写：外部字段文本会先转小写，再与归一化（去空格、转小写）后的关键字做**完全相等**比较，不做模糊包含猜测。因此配置关键字时填写完整文本即可，大小写不影响命中；如果配置了片段式关键字（例如只写“优惠券”而外部文本是“POS - 优惠券”），则无法命中，需要补充完整文本关键字。

映射命中后按 `moduleId → moduleCode → moduleName` 顺序查 `hrm_module` 表解析模块；命中映射但查不到模块记录时只回填映射配置值，模块表无记录时 `module_id` 为空、`module_code` 为空字符串属正常现象。模块字段（`module_id` / `module_code` / `module_name`）在入库与更新时作为整体原子写入，避免三者不一致。

外部工单字段模型（卡片②）定义外部推送字段全集与必填规则，主动拉取字段映射的目标字段也来自这里。

---

## 三、日志拉取默认值

`logPullDefaults` 配置外部同步后自动拉日志的默认参数。

| 配置项 | 说明 |
|--------|------|
| `logPullDefaults.environment` | 默认日志环境，格式为 `分组:子环境`；必须来自日志拉取外部接口配置 |
| `logPullDefaults.commandDataType` | 外部日志命令数据类型 |
| `logPullDefaults.storageMode` | 日志归档方式，如 `local` 或 `ftp` |
| `logPullDefaults.autoAiEnabled` | 日志拉取成功后是否自动发起 AI 分析 |
| `logPullDefaults.aiAgentCode` / `aiProviderCode` | 自动 AI 使用的 Agent / Provider 编码，至少配置一个 |
| `logPullDefaults.autoAiAnalysisCondition.analysisMode` | 历史分析条件：`always` 每次允许，`not_successful` 仅工单没有成功分析记录时允许 |
| `logPullDefaults.autoAiAnalysisCondition.statusFilterEnabled` | 是否启用内部工单状态过滤 |
| `logPullDefaults.autoAiAnalysisCondition.statusCodes` | 允许自动分析的内部状态编码列表 |
| `logPullDefaults.autoLogPullStopCondition.enabled` | 是否启用“自动拉日志停止条件” |
| `logPullDefaults.autoLogPullStopCondition.statusCodes` | 命中后停止自动拉日志的内部状态编码列表；命中任一状态即停止 |
| `logPullDefaults.autoLogPullStopCondition.cancelActiveRecords` | 命中停止状态后，是否自动停止当前工单下仍在运行中的自动日志任务 |

自动 AI 条件只有在“自动 AI 分析”开启时生效，并按 AND 关系检查：自动 AI 已开启、工单状态命中允许列表（启用状态过滤时）、历史分析条件满足、没有正在执行的 AI 任务。状态配置使用系统内部状态编码，不直接填写外部状态文案；外部状态必须先通过“状态映射”转换为内部状态。状态为空、未映射或不在允许列表时，只跳过自动 AI，不影响日志拉取，也不会消耗 Token。

自动拉日志停止条件只影响“同步后自动拉日志”，不影响工单详情页手工拉日志、手工重试和手工 AI 分析。启用后，系统会在自动创建日志任务前检查当前工单内部状态；只要命中任一停止状态，就直接跳过自动日志步骤，并且不再发送无意义的“拉不动日志”失败通知。如果同时打开“停止运行中自动任务”，那么当工单后续流转到这些状态时，系统还会自动取消当前工单下仍在执行中的自动日志任务；这里只处理自动化创建的记录，不会停止手工拉取的任务。

页面入口为“工单同步自动化 → 入库流程 → ⑦ 同步后自动化卡片右上角「日志拉取设置」→ 拉日志默认值”。启用状态过滤后，在“允许的工单状态”中多选内部工作流状态；保存时至少选择一个状态。

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

---

## 四、自动化结果通知

“⑦ 同步后自动化”卡片中的“自动化结果通知”用于接收自动拉日志、日志拉取后的自动 AI 分析结果。启用后选择已有的推送配置服务，并分别控制成功、失败是否发送。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `automationNotification.enabled` | 是否启用自动化结果通知 | `false` |
| `automationNotification.pushIds` | 需要投递的推送配置 ID，可选择多个 | `[]` |
| `automationNotification.success.push` | 日志拉取或 AI 分析成功时是否推送 | `true` |
| `automationNotification.failed.push` | 拉取、创建任务或分析失败/跳过时是否推送 | `true` |
| `automationNotification.messageTemplate` | 消息模板；留空使用系统默认模板 | 空字符串 |

自动化开始时会把当前通知配置快照保存到工单和日志拉取记录中。因此，后续修改配置不会改变已经在运行或已创建的自动化任务的投递渠道和模板。

模板使用 `${变量名}` 格式，可用变量：`${ticket_no}`、`${ticket_title}`、`${merchant_name}`、`${store_name}`、`${stage_label}`、`${status_label}`、`${reason}`、`${detail}`、`${ticket_url}` 等；未识别的变量会原样保留。

部署注意：`start.sh` 使用 Supervisor 将 FastAPI 与 Celery Worker 分成独立进程。自动 AI 通过 FastAPI 内部网关 `/qtr/agent/ai-analysis/send/{agent_code}` 进行跨进程派发，并按 AI 配置中心中的“Agent 并发数”做排队控制。

---

## 五、AI 配置段通用说明

以下 AI 配置段均支持独立选择 Provider 和模型（Provider 与提示词正文在系统管理中维护，这里只选编码）：

| 配置段 | 页签位置 | 说明 |
|--------|---------|------|
| `aiSyncExtract` | 入库流程 ③ | 从标题/描述提取门店、POS/SCO、日志日期、版本 |
| `titleSummaryConfig` | 入库流程 ④ | 缺少标题时自动生成 |
| `translateConfig` | 入库流程 ⑤ | 工单描述翻译，场景开关见总表 |
| `aiClassification` | 入库流程 ⑥ | AI 分类统计，场景开关见总表 |
| `knowledgeConfig` | 入库流程 旁路 | 关闭或手动提炼时执行的知识提炼 |
| `summaryReport` | 通知任务 | 汇总通知 AI 解读 |

每个配置段中的 `modelName` 字段均为可选，留空时自动使用对应 Provider 的默认模型。

### 提取规则与提示词建议（`aiSyncExtract`）

POS/SCO 建议在自定义提示词中明确写成“收银机机台编号”，并要求模型结合字段语义判断，不要对全文数字做简单匹配。推荐加入以下规则：

- `posNo`、`scoNo` 只填写明确属于收银机机台的编号，无法确认时返回 `null`。
- 金额、货币符号、千分位金额、订单号、日期、时间、门店编号和日志行号不能作为 POS/SCO。
- 对“`#2 POS, $44,510.00`”应输出 `posNo=2`；`$44,510.00` 是金额，不能输出 `44`、`44510` 或 `510`。

系统会对模型结果进行安全归一化，策略为**模型结果优先**：金额或千分位文本不会被截取为编号；模型返回的有效编号若命中原文任一机台候选则直接采信；原文出现多个机台候选且模型值不在其中时，保留模型值并记录告警供人工复核。所有冲突和兜底都会写入 AI 执行审计（`machineNumberWarnings`）。

统一提取会保存业务输入指纹 `sourceHash` 和提示词配置指纹 `promptHash`。相同输入重复同步时直接复用成功结果，不重复消耗 Token；描述、标题、门店等业务字段变化才重新提取。

自动拉日志的运行参数以 `extraData.log_pull_hints` 为持久化兜底，并区分外部来源门店编码 `sourceStoreCode` 与日志接口门店 `storeId`：`sourceStoreCode` 只保留外部同步原始值，AI 永远不会反写它；`storeId` 优先采用有效 AI 提取值，无有效值时回退来源编码。若同一商家下同一外部编码匹配到多个不同 `org_no`，系统会记录全部候选门店并跳过自动日志提交，需要人工确认后再执行。

自动拉日志真正提交前，还会按最终运行参数做一次成功记录去重：如果当前工单已经有“相同拉取参数且状态为成功”的日志记录，则这次自动化只记一条“已复用成功日志”的审计，不会重复向外部平台发起相同申请。

日志下载成功后，自动 AI 会优先从已成功日志正文提取版本号并自动创建或复用版本中心记录。

---

## 六、来源与拉取页签

### 6.1 连接配置的继承与覆盖

所有使用飞书多维表格的能力（汇总统计、按人催办、邮箱补全、主动拉取）遵循统一继承顺序：

**模块自身配置 → 多维表格公共配置（`bitableCommon`）→ 统一凭证（`feishuAuth`，仅 appId/appSecret）**

- 模块卡片中的连接字段收在“连接与凭证覆盖（可选）”折叠区内，留空即继承，填写即覆盖；隐藏不清空，展开可恢复。
- “多维表格公共配置”维护默认 `appToken/tableId/viewId/pageSize/filterFormula`。
- “飞书统一凭证”维护 appId/appSecret 基座。

### 6.2 连接解析预览

“来源与拉取”页签的“连接解析预览”卡片按上述继承顺序**实时**展示每个使用方（邮箱补全、主动拉取、汇总统计、按人催办）实际生效的 `appId/appToken/tableId` 及其来源（模块覆盖/公共配置/统一凭证/未配置），只读展示，不需要保存。修改请在各模块卡片的折叠区内填写。

### 6.3 远端同步链接

| 配置项 | 说明 |
|--------|------|
| `remoteSync.enabled` | 是否允许远端拉取任务执行。**不是启动定时任务的按钮**，只控制任务是否放行。关闭时页面不强制校验 `pullUrl/ackUrl/consumer` 必填 |
| `remoteSync.pullUrl` / `ackUrl` | 拉取未同步工单的地址 / 回写交付结果的地址 |
| `remoteSync.consumer` | 消费者标识 |
| `remoteSync.includeClosed` | 拉取时是否包含已关闭工单 |
| `remoteSync.credentialBindingId` | 远端同步凭证绑定（必填），在此卡片内选择 |
| `remoteSync.origin` | 可选非敏感 Origin 请求头 |

### 6.4 飞书多维表格主动拉取

配置定时调度开关、来源系统标识、分页大小、工单号/更新时间/排序字段、强制同步、字段映射；连接与过滤条件收在折叠区内。字段映射支持从飞书读取表格字段元数据。

### 6.5 外部推送多维表格邮箱补全

外部推送传入的 `recordId` 会作为飞书多维表格记录 ID 查询固定字段：`(IT) L1 PIC`、`1.5 当前负责人`、`当前负责人`；连接与凭证收在折叠区内。

---

## 七、通知任务页签

### 7.1 汇总统计通知

- 定时任务或手动触发执行，统计数据源可选 `local` 或 `bitable`
- 可选开启 AI 解读生成摘要
- 多维表格连接、字段与凭证收在“多维表格连接与字段覆盖”折叠区内（数据源=多维表格时展开）

### 7.2 按人催办通知

- 按飞书多维表格中的人员维度统计未处理工单并发送提醒，阈值按分钟配置
- 可手动触发或通过调度任务定时执行
- 连接与凭证收在“连接与凭证覆盖”折叠区内

### 7.3 自定义统计方案

- 在“统计与分类”页签维护统计方案
- 手动执行在“操作”页签，可选“仅预览”或“按方案通知”

---

## 八、发布状态

- 外部推送首先写入 `publish_ready=false`，后台 AI/自动化结束后恢复为可发布。
- `/ticket/sync/pending` 拉取前检查是否有活动 AI 任务；无活动任务时自动恢复 `publish_ready=true`。
- 拉取时写入 `status=pulled` 和租约，30 分钟内不重复返回；超时未回执允许重试。
- `/ticket/sync/ack` 只有 `delivered/success/succeeded` 推进交付版本；`failed` 不阻塞下次拉取。

---

## 常见问题

### Q1: remoteSync.enabled 关闭后有什么影响？

任务执行前检查该开关，关闭时任务不会实际拉取。页面不再强制校验 `pullUrl/ackUrl/consumer` 必填，可以单独保存其他配置项。

### Q2: 如何只关闭内网拉取的翻译？

在“场景 × 步骤 开关总表”中只关闭“⑤ 翻译”行的“远端拉取”列开关。

### Q3: 手动新增工单的自动化怎么配置？

手动新增/编辑的"创建后拉日志"和"自动翻译"在工单新增页配置；同时手动创建场景在本页总表的"手动创建"列也有独立开关（AI 提取 `manualCreateEnabled`、翻译 `translateOnManualCreate`、AI 分类 `runOnManualCreate`、自动识别/拉日志/AI 分析 `automationConfig`、群推送 `sendAfterManualCreate`）。

两处的优先级为"任一开启即执行"：表单勾选等价于本次工单的任务级参数，场景开关则是全局默认；例如表单未勾选自动翻译但 `translateOnManualCreate` 开启，保存后仍会自动翻译；反之表单勾选了翻译而场景开关关闭，也会执行翻译。

手动创建保存成功后，后台按"入库流程"页签的相同执行顺序处理：自动化关注范围判定 → AI 同步提取 → 翻译 → AI 分类 → 同步后自动化（自动识别回写、自动拉日志、自动 AI 分析）→ 向量刷新 → 发布状态收敛与自动群推送。表单中填写的日志拉取参数作为任务级参数优先于 AI 提取结果；未填写时若 `autoLogPullOnManualCreate` 开启，会尝试从 AI 提取结果和映射规则解析日志参数。

### Q4: 如何配置凭证？

远端同步的 `credentialBindingId` 必填（“来源与拉取 → 远端同步链接”卡片内）。在统一凭证管理中创建 `http_api_key` 或 `http_header` 凭证，再创建 `ticket_remote_sync` 类型的业务绑定。

### Q5: 为什么某个开关在卡片里找不到了？

所有场景开关都集中到了“入库流程”页签顶部的“场景 × 步骤 开关总表”，各步骤卡片只保留参数配置；连接类字段收在各卡片“连接与凭证覆盖”折叠区内。

---

## 十、指定工单手动自动化

当需要补跑某一张工单的同步后自动化，但不希望或不能开启“飞书多维表格主动拉取”定时任务时，可在 **操作** 页签的“指定工单手动自动化”卡片中使用。该功能不会修改定时任务配置，也不会触发其他工单。

### 10.1 入口与权限

1. 进入 **工单 → 工单同步配置 → 操作** 页签。
2. 在“指定工单手动自动化”卡片输入需要补跑的**精确工单号**。
3. 选择数据来源后点击 **执行自动化**。
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
- 本次查询忽略常规的 `filterFormula`、时间窗口和自动追加时间过滤，只使用输入工单号构造查询条件。
- 仍需要正确配置飞书连接和字段映射。
- 只允许**一条**精确匹配记录执行；没有匹配或重复时拒绝执行。
- 匹配成功后按既有 `bitable_pull` 场景同步该工单并继续执行后处理自动化。

#### 使用数据库快照

适合飞书记录暂时不可访问、只希望使用已经入库的数据重新触发自动化的场景。

- 系统直接读取数据库中的现有工单 ORM 实体。
- 不会重新调用同步入库，也不会覆盖当前工单字段。
- 会按既有 `bitable_pull` 场景重放后处理自动化。

### 10.4 会执行哪些自动化

两种模式都复用现有 `bitable_pull` 场景，因此仍遵循当前同步自动化配置和自动化关注范围。手动入口不会绕过：自动化关注范围、各子功能启用开关、Provider/Agent/日志参数和通知配置。

### 10.5 常见问题

**Q：提示多维表格中找不到工单？** 先确认工单号完全一致，再检查多维表格连接信息、工单号字段映射和 `viewId` 对应视图的筛选范围。手动模式不会使用常规时间窗口和筛选公式。

**Q：提示找到多条相同工单号？** 请先在多维表格中清理或区分重复记录。系统不会任意选择其中一条。

**Q：为什么执行后没有拉日志或发起 AI？** 该入口仍服从自动化关注范围及总表中的场景开关；请检查工单所属项目/模块是否在范围内，以及日志参数、AI Provider、Agent 等前置条件。

---

## 相关文档

- [统一凭证管理](credential_management.md)
- [工单日志查看器使用说明](ticket_log_viewer.md)
