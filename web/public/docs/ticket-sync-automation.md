# 工单同步自动化说明

## 入口

- 菜单：工单管理 -> 工单同步配置
- 路由：`/ticket/sync-automation`

## 页面目标

这页只管理“外部同步入库”后的自动化行为，包含三类数据源：

- 第三方系统直接调用 `/ticket/sync/external` 推送工单
- 内网系统调用 `/ticket/sync/pending` 拉取外网工单
- 拉取后回写 `/ticket/sync/ack` 的交付状态

手动新增/编辑工单的“创建后拉日志”不在这里配置，走工单新增页；轻量翻译 Provider/提示词走 AI 配置中心（`ticket.ai.translate.*`）。
工单分类统计的 Provider 和提示词正文统一在 AI Provider 管理、AI 提示词管理中维护；同步配置页只选择 Provider 编码、提示词编码和执行场景开关。
旧 `ticket_category_classify_default` 已清理，默认只保留 `ticket_stat_classify_default`。
工单新增/编辑页现在额外提供“手动自动翻译”开关，最终值会写到 `extraData.manualAutomation.autoTranslate`。

## 配置项

### 1. 外部同步基础开关

- `autoRunOnSync`
  - 外部同步入库后是否进入自动化链路。
- `autoTranslateOnSync`
  - 第三方接口直推场景下，是否自动翻译工单描述。
- `defaultPullLimit`
  - 内网拉取未同步工单时的默认拉取数量。
- `remoteSync.sourceSystem`
  - 内网拉取后写入的外部系统标识。

### 2. 远端同步连接

- `remoteSync.enabled`
  - 是否允许远端拉取任务执行。
  - 这不是“启动定时任务”的按钮，只是控制任务是否放行；任务仍然由调度器或手动触发。
  - 关闭时，页面不再强制校验 `pullUrl/ackUrl/consumer` 必填，可直接保存其他配置项。
- `remoteSync.pullUrl`
  - 拉取未同步工单的地址。
- `remoteSync.ackUrl`
  - 回写交付结果的地址。
- `remoteSync.consumer`
  - 消费者标识，用于追踪每个拉取方的回执进度。
- `remoteSync.includeClosed`
  - 拉取时是否包含已关闭工单。
- `remoteSync.autoTranslateOnPull`
  - 仅控制“内网定时拉取外网工单”这条链路是否自动翻译。
  - 这样可以和第三方直推场景独立控制，避免同一工单在不同同步链路里重复翻译。

### 2.1 发布状态与重试

- 外部推送主链路会先写入 `publish_ready=false / publish_status=processing_ai`，后台 AI/自动化结束后再恢复为可发布。
- 如果服务重启导致后台任务未完成，`/ticket/sync/pending` 会在拉取前检查是否仍有活动 AI 任务；没有活动任务时自动恢复 `publish_ready=true`，避免数据长期不对内网发布。
- `/ticket/sync/pending` 返回数据时只写入 `status=pulled` 和 `last_revision` 租约，不直接确认 `delivered_revision`；30 分钟内避免重复返回，超过租约未成功回执则允许重试。
- `/ticket/sync/ack` 只有 `delivered/success/succeeded` 会推进 `delivered_revision`；`failed` 只记录错误和本次 revision，不会阻止下次继续拉取同一版本。

### 2.5 工单手动新增/编辑

- `auto_translate`
  - 工单页“手动自动翻译”开关。
  - 关闭后，手动新增/编辑不会再调用轻量翻译。
  - 该值会保存在 `extraData.manualAutomation.autoTranslate`，方便后续编辑回显。

### 3. 识别规则

- `projectMappings`
- `moduleMappings`
- `vendorMappings`
- `storeMappings`
- `statusMappings`
- `assigneeMappings`
- `posPatterns`
- `scoPatterns`
- `versionPatterns`
- `externalSyncBitable`
  - 外部推送按 `recordId` 查询飞书多维表格记录并补齐人员邮箱。
  - 需要配置 `enabled/appToken/tableId`，可选 `viewId/appId/appSecret`。
  - 固定读取字段：`(IT) L1 PIC` -> `reporterName`，`当前负责人` -> `currentAssigneeName`，`1.5 当前负责人` -> `internalOwner`。

### 4. 日志拉取默认值

- `logPullDefaults`

这部分用于外部同步后自动拉日志的默认参数，页面已加宽显示，避免字段过多时看不全。

### 5. 提示词模板

- `promptTemplates.classificationHint`
  - 后续扩展 AI 识别时复用的分类提示词。

### 5.5 工单分类 AI 统一配置

- `ticket.ai.category.classify.enabled`
  - 旧分类字段 `category_name` 的轻量自动分类总开关。
- `ticket.ai.category.classify.provider.code`
  - 默认 Provider 编码；当 `aiClassification.providerCode` 为空时作为兜底。
- `ticket.ai.category.classify.prompt.code`
  - 默认提示词编码；当 `aiClassification.promptCode` 为空时作为兜底，历史旧值会自动映射到 `ticket_stat_classify_default`。
- `ticket.sync.automation.aiClassification`
  - 控制分类统计是否启用，以及外部同步、远端拉取、手动创建场景是否执行。
  - 只保存 Provider 编码和提示词编码选择；提示词正文统一在 AI 提示词管理维护。
  - 可配置状态变更后是否执行 AI 分类统计，并通过 `statusChangeTriggerStatuses` 指定一个或多个目标状态。
  - 历史 `promptContent` 会保留作为旧配置兜底，但不再作为新编辑入口。
- `ticket.sync.automation.statClassification`
  - 维护工单类型、根因分类、解决方式、关闭结果枚举；它是业务枚举配置，不属于 AI Provider/Prompt 底座配置。

### 5.6 分类统计回填

- 自动处理数据：标题、描述、最近评论、当前字段和统计枚举。
- 自动触发场景：外部同步入库、远端拉取入库、手动创建工单、命中配置的状态变更、批量重归类。
- 防重复规则：非强制场景下，只有核心分类字段完整且内容未变化时才跳过；内容变化或任一核心分类字段缺失时会继续归类。
- 核心分类字段不包含 `module_name` 和 `severity`：前者来自项目/模块映射，后者是工单自身严重程度属性。
- 回填字段：`category_name`、`issue_type_id`、`issue_type_name`、`module_name`、`severity`、`root_cause_type`、`solution_type`、`resolution_code`、`resolution_name`、`root_cause`、`solution`、`is_problem`。
- 执行摘要写入 `extra_data.ai_classification`，保留来源 hash、Provider、Prompt、置信度和模型原始结果。

### 6. 工单通知配置

- `feishuAuth`
  - `appId` / `appSecret`：统一飞书应用凭证。
  - `groupPush` / `personReminder` / `summaryReport` 默认继承该凭证，也支持各自覆盖。
- `groupPush`
  - `enabled`：是否启用工单群消息推送。
  - `sendMode`：发送模式（`push_config` / `feishu_app` / `hybrid`）。
  - `pushIds`：机器人推送渠道，候选项来自“推送配置管理”（`qtr_push_target`）。
  - `appChatIds`：飞书应用身份发群的 `chat_id` 列表。
  - `autoPushStatuses`：自动推送状态条件，只有工单 `status` 命中该列表才会自动推送；留空表示不按状态限制。
  - `priorityRoutes`：按优先级分流路由（例如 P1 -> P1 群，P2 -> P2 群，P3/P4 -> P3/P4 群）。
  - `sendAfterExternalSync` / `sendAfterRemotePull`：自动触发场景开关。
  - 自动推送幂等：同一工单自动推送成功一次后会写入 `group_push_sent_once=true`，后续自动触发会跳过并记录日志；手动触发不受该限制。
  - 并发防重：自动推送发送前会先抢占数据库处理锁（`group_push_processing`），同工单并发任务会在发送前直接跳过，避免秒级重复推送造成重复发群。
  - `template` / `manualTemplate`：模板变量渲染，手动模板留空时回退自动模板。
  - 常用模板变量：`${ticket_no}` `${ticket_title}` `${ticket_status}` `${assignee_name}` `${reporter_name}` `${reporterName}` `${store_info}` `${storeInfo}` `${ticket_url}` `${sync_source_record_url}`。
- `personReminder`
  - `enabled`：是否启用按人催办。
  - `sendMode`：发送模式（`push_config` / `feishu_app` / `hybrid`）。
  - `dataSource`：统计数据源（`bitable` / `local`）。
  - `bitable` 模式：
    - `appToken` / `tableId` / `viewId`：飞书多维表格数据源。
    - `filterFormula`：飞书 `records/search` 的 `filter` JSON 条件对象，支持 JSON 字符串或对象。
    - `personField` / `timeField` / `thresholdMinutes`：按人聚合与超时判定配置。
  - `local` 模式：
    - 统计来源为本地 `ticket` 表，按“当前处理人”聚合；
    - `timeField` 使用工单时间字段（`update_time/create_time/started_at/resolved_at/closed_at`）；
    - `thresholdMinutes` 仍用于超时阈值判定。
  - `messageTemplate`：催办模板，支持变量渲染。
  - 催办链路：按字段聚合超时记录 -> 关联系统用户邮箱 -> 按模式发送（机器人推送或应用私信邮箱）。
- `summaryReport`
  - `enabled`：是否启用工单汇总统计通知。
  - `sendMode`：发送模式（`push_config` / `feishu_app` / `hybrid`）。
  - `dataSource`：统计数据源（`local` / `bitable`）。
  - `local` 模式：
    - `timeField`：本地工单时间字段（`create_time/update_time/closed_at/resolved_at/started_at`）。
  - `bitable` 模式：
    - `appToken` / `tableId` / `viewId`：飞书多维表格数据源。
    - `filterFormula`：飞书 `records/search` 的 `filter` JSON 条件对象，支持 JSON 字符串或对象。
    - `statusField` / `categoryField` / `priorityField`：统计字段名映射。
    - `bitableTimeField`：多维记录时间字段（为空时回退记录创建时间）。
    - `pageSize`：分页拉取大小，最大500。
  - `windowMinutes` / `endDelayMinutes`：滚动窗口与延迟窗口。
  - `startTime` / `endTime`：固定统计窗口（配置后优先于滚动窗口）。
  - `includeClosed`：是否包含已关闭工单。
  - `aiEnabled` / `aiProviderCode` / `aiPromptCode`：启用 AI 汇总解读与自定义提示词。
  - `messageTemplate`：汇总模板，支持状态/分类/优先级统计变量，以及 `${data_source}` `${ai_summary}`。

### 6.1 自动分类管理（同步配置页内置工具）

- 一键统计未归类：`GET /ticket/sync/auto-category/stats`
  - 返回总工单数、已归类数、未归类数、未归类占比。
  - 该接口只统计，不执行自动归类；需要处理未归类工单时调用批量重归类接口。
  - 后端入口由 `TicketBatchReclassificationService.get_uncategorized_ticket_statistics_services` 承接，不经过外部同步入库主服务。
- 批量重归类：`POST /ticket/sync/auto-category/reclassify`
  - `ticketIds`：指定要重归类的工单 ID 列表，填写后优先按指定工单执行
  - `strategy`：`ai` / `regex`
  - `aiPromptCode`：AI 归类提示词编码（可选，空则走当前分类统计配置）
  - `regexRules`：正则规则数组（元素含 `pattern/category/flags`）
  - `onlyUncategorized`：仅处理未归类
  - `allTickets`：全量扫描（否则按分页）
  - `forceReclassify`：强制覆盖已有分类
  - 后端入口由 `TicketBatchReclassificationService.batch_reclassify_ticket_categories_services` 承接；AI 策略继续调用 `TicketAutoClassificationService`，正则策略在重归类服务内完成。
  - 服务日志会记录筛选条件、每条工单处理状态、跳过原因、AI/正则执行结果和最终汇总。

## 逻辑梳理

### 第三方直推

1. 外部系统调用 `/ticket/sync/external`
2. 服务端只接受约定字段的驼峰/下划线写法，不再猜测第三方自定义字段名；请求读取和字段归一化由 `TicketExternalSyncRequestService` 承接，字段不符合契约时直接返回 422，不入库
3. 必填字段默认是 `ticketNo`、`description`、`internalPriority`、`ticketVender`、`ticketModle`、`createTime`、`reporterName`，可通过 `externalSyncRequiredFields` 调整
4. 可选字段包括 `title`、`customerPriority`、`reason`、`ticketStatus`、`currentAssigneeName`、`internalOwner`、`ticketAssignee`、`ticketAssigneeEmail`、`reporterEmail`、`ticketStore`、`ticketPos`、`ticketSco`、`ticketUrl`、`recordId`
5. 原始请求体会完整保存到 `extraData.raw_payload`，外部字段快照会保存到 `extraData.external_field_mapping`，供通知和排查复用
6. 服务端只在第三方直推边界执行外部映射：`ticketVender` 映射项目/商家，`ticketModle` 映射模块，`ticketStatus` 映射内部状态，`reporterName/currentAssigneeName/internalOwner` 按人员映射表和多维邮箱映射到本地用户
7. 映射失败时不阻断入库；项目、模块、处理人等字段允许只保留原始名称或文本，后续由人工补充或配置修正
8. `reporterName` 会写入报告人/1线处理人，`currentAssigneeName` 写入当前处理人，`internalOwner` 写入内部负责人
9. 如果推送体包含 `recordId` 且启用 `externalSyncBitable`，会查询飞书多维表格记录邮箱并写入 `extraData.external_field_mapping`，供内部用户匹配和群消息 @ 人复用
10. 如果推送体包含 `ticketUrl`，会写入工单详情链接 `ticket_url`
11. 门店字段 `ticketStore` 会优先按“商家ID + 门店配置（sap_org_no）”匹配；命中则保存配置门店，未命中保留原始值
12. 入库后的延后后处理任务（翻译、标题AI、自动化、群推送）优先投递 Celery；当 Celery Worker 不可用时回退 FastAPI 本地后台任务
13. 接口返回体会附带 `deferredDispatch`，可用于判断本次由 `celery` 还是 `background` 执行
14. 如开启 `autoTranslateOnSync`，会自动翻译描述
15. 如开启 `autoRunOnSync` 或请求里携带自动化配置，会继续走识别、拉日志、AI 分析
16. 自动拉日志新增参数门槛：仅当可确定 `vendorId + storeId + posNo/SCO + modifyTime(日期)` 才会提交拉取；参数不齐全时自动跳过并记录步骤原因

### 内网拉取外网工单

1. 定时任务调用 `/ticket/sync/pending`
2. 只有 `remoteSync.enabled=true` 才会真正执行拉取
3. 每次拉取完成后，服务端会按远端返回的内部字段入库，不再执行 `ticketVender/ticketModle/statusMappings/assigneeMappings` 等外部映射
4. 是否自动翻译由 `remoteSync.autoTranslateOnPull` 单独控制
5. 项目和模块只通过 `projectCode/moduleCode` 绑定本地 ID；业务码未命中时只保留远端名称，不使用远端 `projectId/moduleId`
6. 当前处理人只通过邮箱优先、名称兜底匹配本地用户；未命中时只保留处理人名称，不使用远端 `currentAssigneeId`
7. 远端携带的 `extraData.raw_payload`、`extraData.log_pull_hints`、`versionKey`、项目/模块业务码等内部字段会继续保留和复用
8. 远端拉取仍保留现有后处理能力：翻译、标题/分类、自动日志拉取、自动 AI 分析、群推送和发布就绪状态
9. 如命中 `groupPush.sendAfterRemotePull` 且 `groupPush.enabled=true`，会按模板推送到配置群

### 回写交付状态

1. 入库成功或失败后，服务端调用 `/ticket/sync/ack`
2. 远端系统据此更新拉取状态

### 按人催办（手动与定时）

1. 页面可通过用户ID或邮箱预览“本人名下超时记录统计”。
2. 页面可直接手动触发催办发送。
3. 可通过调度任务 `module_task.scheduler_maintenance.ticket_person_overdue_reminder` 定时执行。
4. 定时任务支持任务级覆盖参数：`appToken`、`tableId`、`viewId`、`filterFormula`、`personField`、`timeField`、`dataSource`、`pageSize`。
5. 覆盖规则：任务参数中对应字段为非空时优先使用任务值；未配置或为空字符串时继续使用“工单同步配置”里的 `personReminder` 全局配置。
6. 覆盖参数既可平铺在任务 JSON，也可放入 `personReminder` 对象，例如：
   `{"isAll": true, "appToken": "...", "tableId": "...", "personField": "当前负责人", "timeField": "更新时间"}`
   或 `{"isAll": true, "personReminder": {"appToken": "...", "tableId": "...", "filterFormula": {"conjunction":"and","conditions":[{"field_name":"状态","operator":"isNot","value":"已关闭"}]}}}`。
7. 统计数据源可选：
   - `bitable`：从飞书多维表格读取后按人聚合；
   - `local`：从本地工单表按当前处理人聚合。
8. 触发后会记录关键日志：配置是否启用、数据源、数据读取结果、人员匹配结果、发送结果与失败原因。

### 汇总统计通知（手动与定时）

1. 页面支持手动触发 `POST /ticket/sync/notify/summary/run`，可选传开始/结束时间。
2. 定时任务可执行 `module_task.scheduler_maintenance.ticket_summary_report`。
3. 统计数据源可选：
   - `local`：本地工单表统计；
   - `bitable`：飞书多维表格统计。
4. 统计结果按状态/分类/优先级聚合后发送到指定渠道（机器人或飞书应用）。
5. 可选开启 AI 解读，按自定义 Provider/Prompt 生成 `${ai_summary}` 并注入消息模板。
6. 配置缺失时会返回 `skipped + skipReason`，并写日志，不会抛异常导致接口失败。
7. `hybrid` 模式会自动降级：一路配置缺失时仍发送另一路，避免整体通知丢失。

## 说明

- `remoteSync.enabled` 不是“手动启动定时任务”的开关，而是任务执行前的放行条件。
- 手动新增工单和外部同步是两条独立链路，配置不要混用。
- 如果你只想关闭“内网拉取链路”的自动翻译，优先改 `remoteSync.autoTranslateOnPull`，不要去动第三方直推的 `autoTranslateOnSync`。

## 业务码匹配

- `project_code`
  - 项目业务码，建议人工维护并在内网/公网之间同步保持一致，仅内网 `remote_pull` 拉取公网 pending 工单后再入库时使用。
- `module_code`
  - 模块业务码，建议跟随项目一起同步维护；仅内网 `remote_pull` 场景会结合 `project_code` 按业务码直接落库。
- 兼容顺序
  - 外部推送和飞书多维主动拉取：只看 `ticketVender` / `ticketModle` 对应的 `projectMappings` / `moduleMappings`
  - 内网 `remote_pull`：优先通过 `projectCode/moduleCode` 匹配本地项目/模块，未命中时只保留远端项目/模块名称
  - 如果公网和内网要使用同一套业务码，优先人工维护项目和模块业务码，不依赖跨环境 ID 一致
