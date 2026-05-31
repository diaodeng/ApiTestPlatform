# 工单外部同步与内网拉取设计

## 目标

为双环境部署补齐一套通用同步链路：

- 公网环境接收外部工单系统推送。
- 内网环境按消费者标识拉取“未拉取或有新 revision”的工单。
- 同一工单支持多次更新并再次下发，不再依赖单一布尔值判断“是否已同步”。
- 拉取后可按规则自动识别项目、模块、商家、门店、POS/SCO 编号，并串联日志拉取与 AI 分析。

## 核心结论

- 当前已经可以实现。
- “是否已被拉取”不再用单一布尔值，而是用 `revision + consumer.delivered_revision` 判断。
- 自动识别、相似工单检索、自动拉日志、自动 AI 的执行状态会回写到 `extraData.external_sync.sync_state.automation`，方便定位卡在哪一步。
- 识别规则尽量做成参数配置，当前版本采用“映射规则 + 正则 + 默认参数”的通用方案，避免把某个工单系统的话术写死在代码里。

## 新增接口

### `POST /ticket/sync/external`

用途：

- 外部工单系统推送或更新工单。
- 以 `ticketNo` 为幂等键，已存在则更新，不存在则创建。
- 每次推送都会递增 `external_sync.revision`。

关键入参：

- `ticketNo`
- `title`
- `description`
- `source.system`
- `source.recordId`
- `rawPayload`
- `automation`

### `GET /ticket/sync/pending`

用途：

- 内网系统按 `consumer` 拉取待同步工单。
- 只返回当前 `revision` 大于该消费者已交付 revision 的工单。
- 拉取成功后会把该消费者的交付 revision 写回工单 `extraData.external_sync.sync_state.consumers`。
- 只会返回带有 `external_sync.revision` 的同步工单，不会把普通人工工单误算进来。

关键查询参数：

- `consumer`
- `limit`
- `includeClosed`

### `POST /ticket/sync/ack`

用途：

- 可选回执接口。
- 内网系统可把“已处理/处理失败/部分成功”等结果回写到消费者状态，便于公网环境追踪。

## 同步状态模型

状态信息统一落在 `ticket.extra_data.external_sync`：

- `revision`: 当前同步版本，每次外部推送递增。
- `sourceSystem` / `sourceRecordId` / `sourceRecordUrl`: 来源标识。
- `lastImportedAt`: 最近一次导入时间。
- `sync_state.status`: 最近一次交付状态。
- `sync_state.last_consumer`: 最近拉取消费者。
- `sync_state.last_batch_id`: 最近一批次 ID。
- `sync_state.consumers.{consumer}.delivered_revision`: 指定消费者已交付到的 revision。
- `sync_state.automation`: 自动识别与自动化链路状态。

这套结构可以解决两个问题：

- 工单被拉过一次后，如果外部又更新了内容，内网仍然能再次拉到。
- 支持未来一个公网环境被多个内网消费者分别拉取。

## 自动化链路

执行位置：

- 自动化发生在“接收这条工单数据的一侧”。
- 如果公网环境只是外部入口，而真正要识别归属、拉日志、跑 AI 的是内网环境，那么内网环境在拉到数据后再调用 `POST /ticket/sync/external` 入站即可复用同一套自动化逻辑。
- 这样公网和内网都可以共用统一的“入站同步接口”，而不是为不同部署形态再拆两套实现。

当前版本的自动化以“可配置规则 + 正则”为主，不直接写死工单系统话术：

- 规则配置键：`ticket.sync.automation`
- 支持维护：
  - `projectMappings`
  - `moduleMappings`
  - `vendorMappings`
  - `storeMappings`
  - `posPatterns`
  - `scoPatterns`
  - `versionPatterns`
  - `logPullDefaults`
  - `promptTemplates`

自动化步骤：

1. 识别项目、模块、商家、门店、POS/SCO、版本号。
2. 检索相似工单。
3. 若日志参数足够完整，则自动创建日志拉取任务。
4. 若启用自动 AI，则优先通过“日志拉取成功后自动 AI”链路继续执行。

## 失败记录

自动化状态写入 `extraData.external_sync.sync_state.automation`：

- `status`
- `current_step`
- `last_error`
- `steps.identify`
- `steps.similar_ticket`
- `steps.log_pull`
- `steps.ai_analysis`

日志拉取和 AI 分析的详细失败原因仍以原有表为准：

- 日志拉取看 `ticket_log_pull_record`
- AI 分析看 `ticket_ai_analysis_task`

## 当前边界

当前版本已经支持：

- revision 化同步状态
- 外部推送 / 内网拉取 / 可选回执
- 规则化识别
- 自动串联日志拉取与 AI 分析状态

当前版本暂未支持：

- 真正的通用 LLM 字段识别
- 前端同步状态专门面板
- 拉取失败自动重放
- 基于 `source.system + source.recordId` 的全局去重主键，当前主幂等键仍然是 `ticketNo`

如果后续要接 AI 识别，优先在 `ticket.sync.automation.promptTemplates` 基础上扩展，不建议再把规则写回代码里。
