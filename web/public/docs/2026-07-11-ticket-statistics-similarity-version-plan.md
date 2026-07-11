# 2026-07-11 工单统计、相似工单、版本治理与独立详情页方案

## 结论

本方案只做后续实施设计，不包含本次代码改动。

1. 工单详情页相似工单查询不应每次调用外部 Embedding。详情页应优先复用当前工单已保存的向量；只有外部入库、手动新增、手动编辑、导入、RCA/知识沉淀等数据变化入口负责刷新向量。
2. 工单统计页的默认时间不能简单写成“最近一周”。如果只是向前滚动 7 天，应命名为“最近 7 天”；如果要按每周四 18:00 作为周起点，应引入“业务周”配置。
3. 当前 `ticket_statistics_daily` 是自然日快照，无法精确支持“周四 18:00 到下周四 18:00”这类非自然日边界的快照周统计。要保证快照口径，需要新增业务周期快照或更细粒度快照。
4. 已发版工单的快速维护建议走独立的版本治理能力，不把“已发版”塞进主流程状态；通过版本字段、发布/验证时间和批量操作支撑统计。
5. 统计页趋势明细表头应像工单列表一样使用用户级配置持久化。
6. 相似工单“系统详情”应打开真正独立的详情页组件，不再复用工单列表页组件再用隐藏逻辑规避列表展示。

## 当前现状

### 相似工单

现有向量刷新已经支持幂等复用：`TicketEmbeddingService.vectorize_ticket` 会按向量文本、字段配置、模型、版本和维度计算 `content_hash`，未变化时复用 `embedding_record`，不再调用外部 Embedding。

实际问题在详情页相似查询链路：`TicketService.get_messages_services` 当前拼接当前工单文本后调用 `TicketEmbeddingService.search_tickets`。当 Provider 是 `embedding` 或 `qdrant` 时，查询文本本身仍需要调用外部 Embedding 生成查询向量，所以每次打开详情页都会产生外部请求。

### 统计页

当前统计页：

1. 支持 `realtime/snapshot` 两种统计口径。
2. 快照口径读取 `ticket_statistics_daily`。
3. `ticket_statistics_daily` 已支持全局自然日快照和项目/模块/工单类型叶子维度自然日快照。
4. 统计页时间范围当前为空。
5. 统计块和趋势块已有用户级显示配置，趋势明细表头仍硬编码。

### 版本治理

工单主表已具备版本治理基础字段：

1. `affected_version`：问题发生/分析版本。
2. `planned_fix_version`：计划修复版本。
3. `fixed_version`：实际修复版本。
4. `released_version`：实际发版版本。
5. `released_at`：发版时间。
6. `verified_at`：验证时间。

这些字段可以支撑“哪个版本问题多”“哪个版本解决了什么问题”，不需要新增“已发版”主流程状态。

### 独立详情页

当前已有隐藏路由 `#/ticket/detail/:ticketId`，但仍复用 `web/src/views/ticket/index.vue`。页面内部通过 `standaloneDetailMode` 隐藏列表区域，并跳过列表接口。这个方案可以避免明显列表查询，但仍加载了大量列表页状态、hook、弹窗和副作用，不是真正独立的详情页。

## 需求拆解

### 1. 详情页相似工单不重复向量化

目标：

1. 打开详情页展示相似工单时，优先使用当前工单已保存的向量查询。
2. 当前工单向量缺失或过期时，详情页会按当前 Provider 配置同步刷新向量后再查询相似工单。
3. 外部入库、编辑新增、导入、RCA、关闭知识沉淀等数据变化入口自动刷新向量。
4. 向量内容未变化时自动跳过外部接口。

推荐设计：

1. 新增相似查询子服务，例如 `server/modules/ticket/service/ai/ticket_similarity_query_service.py`。
2. 提供公开方法 `search_similar_tickets_by_ticket(query_db, ticket_id, limit=5)`。
3. 查询流程：
   - 读取当前相似工单配置。
   - 根据当前工单和配置字段调用 `build_ticket_text` 生成标准向量文本。
   - 计算当前 `content_hash`。
   - 按 `object_type=ticket/object_id=ticket_id/model/version` 读取 `embedding_record`。
   - 如果记录存在、维度一致、`content_hash` 一致，直接使用记录中的 `embedding` 作为查询向量。
   - 如果 Provider 是 `embedding`，用该查询向量与库内 `embedding_record` 做相似度计算。
   - 如果 Provider 是 `qdrant`，用该查询向量请求 Qdrant 查询相似点。
   - 过滤当前工单自身。
4. 向量缺失或过期时：
   - 详情接口同步刷新当前工单向量，刷新成功后返回相似工单和 `similarEmbeddingStatus=ready`。
   - 刷新失败时返回空相似工单和 `similarEmbeddingStatus=error`。
   - 刷新过程按当前 Provider 严格执行，`embedding/qdrant` 会调用外部 Embedding，`local_hash` 只生成本地哈希向量。

数据变化自动刷新：

1. 手动新增：继续走 `sceneTriggers.manualCreate`。
2. 手动编辑：继续走 `sceneTriggers.manualUpdate`。
3. 外部同步入库：继续走 `sceneTriggers.externalSync`。
4. 多维主动拉取：继续走 `sceneTriggers.bitablePull`。
5. 远端拉取：继续走 `sceneTriggers.remotePull`。
6. Excel 导入：继续走 `sceneTriggers.import`。
7. 关闭知识沉淀：继续走 `sceneTriggers.closeKnowledge`。
8. RCA 保存、人工确认 AI 结论写回主结论时，如这些字段进入向量字段列表，也应触发对应场景刷新。可新增 `sceneTriggers.rcaUpdate`，或者复用 `manualUpdate`，但文案要明确。

优化建议：

1. 相似查询不要再用临时拼接文本，应统一使用 `TicketEmbeddingService.build_ticket_text`，避免入库文本和查询文本不一致。
2. 详情页相似工单可懒加载：概览打开时先展示详情，用户展开“相似工单”时再查询。
3. 后端日志必须区分：
   - `similar_query_from_cache`：复用当前工单已保存向量查询。
   - `embedding_rebuild_skipped`：向量刷新入口幂等跳过。
   - `embedding_missing_for_query`：详情查询发现向量缺失但未同步调用外部接口。

### 2. 已发版工单快速维护与版本问题统计

目标：

1. 快速维护已经发版工单的版本、发版时间、验证时间和状态。
2. 统计哪个版本问题多、是什么问题。
3. 统计哪个版本解决了什么问题。

不推荐做法：

1. 不新增一个“已发版”主流程状态来承载统计。
2. 不把发版信息塞进 `extra_data`。
3. 不用 `resolved_at` 代表真实 Bug 修复完成。

推荐字段口径：

| 字段 | 语义 | 用途 |
|---|---|---|
| `affected_version` | 问题发生/分析版本 | 统计哪个版本问题多 |
| `planned_fix_version` | 计划修复版本 | 排期和治理 |
| `fixed_version` | 实际修复版本 | 统计哪个版本修复了哪些问题 |
| `released_version` | 实际发版版本 | 统计哪个版本发布了哪些修复 |
| `released_at` | 发版时间 | 发版闭环 |
| `verified_at` | 验证时间 | 验证闭环 |
| `issue_id` | 真实问题实例 | 去重统计真实问题数 |

第一阶段：批量维护能力。

1. 工单列表增加批量操作：
   - 批量设置计划修复版本。
   - 批量设置实际修复版本。
   - 批量设置发版版本。
   - 批量设置发版时间。
   - 批量设置验证时间。
   - 批量标记发版完成。
   - 批量标记验证完成。
2. 后端新增版本治理子服务，例如 `server/modules/ticket/service/core/ticket_release_service.py`。
3. 控制器只接收参数、鉴权和 `run_in_threadpool` 包装，不承载业务规则。
4. 服务层负责：
   - 批量校验工单是否存在。
   - 只更新版本治理字段。
   - 写入 `TicketEventType.DEPLOYED/VERIFIED` 事件。
   - 调用 `TicketProcessingMetricService` 写 `released_at/verified_at`。
   - 必要时刷新快照或提示快照次日生效。

第二阶段：版本统计能力。

新增版本统计页面或在统计页增加“版本治理”页签：

1. 按发生版本统计：
   - 工单数。
   - 真实问题数。
   - Issue 数。
   - Top 模块。
   - Top 工单类型。
   - Top 细分问题。
   - Top 根因分类。
   - 未处理数。
   - 未关闭数。
2. 按修复/发版版本统计：
   - 修复工单数。
   - 修复 Issue 数。
   - 已发版数。
   - 已验证数。
   - 未验证数。
   - 关闭结果分布。
   - 解决方式分布。
3. 明细列表：
   - 支持按版本点击下钻。
   - 支持批量维护。
   - 表头配置可复用用户级配置。

第三阶段：版本快照。

如果版本统计用于正式周报，建议新增快照：

1. `ticket_version_statistics_daily`：按自然日冻结版本维度。
2. 或扩展 `ticket_statistics_daily` 的叶子维度，但不建议继续把所有维度塞进一个表，避免快照表膨胀和口径混乱。

### 3. 统计页详情列表表头可配置

目标：

1. 统计页趋势明细表头可配置。
2. 配置像工单列表一样按当前用户持久化保存。

推荐设计：

1. 新增用户配置：
   - `configType=ticket`
   - `configKey=ticket_statistics_detail_columns`
2. 默认列：
   - `bucket`：周期，必选。
   - `newCount`：新增。
   - `firstRespondedCount`：已响应。
   - `processedCount`：已处理。
   - `processedInNewCount`：新增已处理。
   - `processRate`：处理率。
   - `resolvedCount`：处置完成。
   - `closedCount`：关闭。
   - `netIncrease`：净增。
   - `unprocessedBacklog`：未处理存量。
   - `openBacklog`：未关闭存量。
   - `problemCount`：Bug。
   - `nonProblemCount`：非 Bug。
   - `supportCount`：支持类。
   - `avgFirstResponseSeconds`：平均响应耗时。
   - `avgFirstProcessSeconds`：平均处理耗时。
   - `problemPatternCounts`：Top 细分问题。
   - `moduleCounts`：Top 模块。
3. 配置弹窗：
   - 现有“显示配置”保留统计块和趋势块。
   - 增加“趋势明细列”配置区，或新增“明细列设置”按钮。
4. 兼容策略：
   - 历史用户没有该配置时使用默认列。
   - 后续新增列时通过 `configVersion` 自动补齐一次。
   - 必选列不允许取消。

### 4. 统计页默认时间范围与业务周起点

目标：

1. 支持配置默认时间范围。
2. 避免把滚动 7 天误称为“最近一周”。
3. 支持业务周起点，例如每周四 18:00。
4. 周统计粒度可按业务周分桶。

推荐配置模型：

配置位置可以先用系统参数，后续如需要个人偏好再叠加用户配置。

系统参数建议：

```json
{
  "defaultRangeMode": "business_week",
  "rollingDays": 7,
  "businessWeekStartWeekday": 4,
  "businessWeekStartTime": "18:00:00",
  "businessWeekDefaultWindow": "current",
  "trendWeekBucketMode": "business_week"
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `defaultRangeMode` | 默认时间模式，支持 `rolling_days/business_week/current_month/custom_empty` |
| `rollingDays` | `rolling_days` 模式下向前滚动天数，文案应显示“最近 N 天” |
| `businessWeekStartWeekday` | 业务周开始星期，建议 1-7 表示周一到周日 |
| `businessWeekStartTime` | 业务周开始时间，例如 `18:00:00` |
| `businessWeekDefaultWindow` | `current` 表示当前业务周，`previous_completed` 表示上一个完整业务周 |
| `trendWeekBucketMode` | 周趋势分桶模式，支持 `calendar_week/business_week` |

默认时间范围规则：

1. `rolling_days`：
   - 例如 `rollingDays=7`。
   - 页面文案显示“最近 7 天”。
   - 适合临时滚动监控。
2. `business_week + current`：
   - 计算最近一个不晚于当前时间的业务周起点。
   - 开始时间为该起点。
   - 结束时间为当前时间，或按页面配置使用业务周结束时间。
   - 页面文案显示“当前业务周”。
3. `business_week + previous_completed`：
   - 取上一个已经完整结束的业务周。
   - 例如业务周起点是周四 18:00，则统计上一个周四 18:00 到本周四 18:00。
   - 适合周报、复盘和稳定对比。

示例：业务周从周四 18:00 开始。

| 当前时间 | current 默认范围 | previous_completed 默认范围 |
|---|---|---|
| 周三 10:00 | 上周四 18:00 到当前时间 | 上上周四 18:00 到上周四 18:00 |
| 周四 17:59 | 上周四 18:00 到当前时间 | 上上周四 18:00 到上周四 18:00 |
| 周四 18:01 | 本周四 18:00 到当前时间 | 上周四 18:00 到本周四 18:00 |

前端实现建议：

1. 统计页初始化先读取统计时间配置。
2. 根据配置生成 `dateRange`。
3. 查询按钮仍允许用户手动改时间。
4. 重置按钮恢复配置默认时间，而不是清空。
5. 页面文案明确显示：
   - “最近 7 天”
   - “当前业务周：2026-07-09 18:00 至 当前”
   - “上一完整业务周：2026-07-02 18:00 至 2026-07-09 18:00”

后端实现建议：

1. 新增纯工具 `ticket_statistics_time_util.py`，只处理时间窗口计算，不访问数据库。
2. 后端统计接口可以接收前端传入的 `beginTime/endTime`，不强依赖后端默认。
3. 如果要让通知任务、定时任务和页面完全一致，应由后端提供“解析默认统计时间范围”的接口，前端只展示后端返回的范围。

### 5. 业务周与快照口径的关系

当前自然日快照不能精确支持周四 18:00 起点的业务周。

> 2026-07-11 后续实现补充：已新增 `ticket_statistics_period_snapshot` 业务周期快照表和 `ticket_business_week_statistics_snapshot` 任务，快照口径业务周统计现在读取周期快照，不再使用本节的临时限制方案。

原因：

1. `ticket_statistics_daily` 每行代表一个自然日。
2. 业务周边界是周四 18:00，不是自然日 00:00。
3. 一个周四自然日会被拆成两段：
   - 00:00 到 18:00 属于上一个业务周。
   - 18:00 到 24:00 属于下一个业务周。
4. 当前自然日快照无法把同一天拆成两个业务周片段。

因此，如果统计页选择 `statisticsMode=snapshot` 且 `granularity=week`，要支持业务周有三种方案。

#### 方案 A：业务周只支持实时口径

实现成本最低。

规则：

1. 默认时间范围可以按业务周生成。
2. 趋势 `granularity=week` 可以按业务周实时分桶。
3. 快照口径仍按自然日/自然周聚合。
4. 当用户选择业务周分桶 + 快照口径时，页面提示“当前快照为自然日冻结，不支持非自然日业务周精确分桶，请切换实时口径或使用自然周”。

优点：

1. 改动小。
2. 不改快照表结构。
3. 快速满足页面默认时间范围需求。

缺点：

1. 周报快照无法按周四 18:00 精确冻结。
2. 快照周统计和实时业务周统计可能不一致。

#### 方案 B：新增业务周期快照

推荐用于正式周报。

新增表建议：`ticket_statistics_period_snapshot`。

核心字段：

| 字段 | 说明 |
|---|---|
| `period_type` | `business_week/month/custom` |
| `period_key` | 例如 `2026-BW28` |
| `period_start` | 周期开始时间，例如周四 18:00 |
| `period_end` | 周期结束时间 |
| `snapshot_scope` | `all/leaf` |
| `project_id/module_id/issue_type_id` | 维度字段 |
| 指标字段 | 复用 `ticket_statistics_daily` 的提交、响应、处理、关闭、耗时等指标 |

任务规则：

1. 新增业务周快照任务。
2. 默认在业务周结束后几分钟执行，例如周四 18:05。
3. 按 `period_start <= submit_time < period_end` 统计完整业务周。
4. 结果 upsert，允许补跑。
5. 统计页选择快照口径 + 业务周分桶时读取该表。

优点：

1. 支持正式周报稳定口径。
2. 能精确支持周四 18:00 起点。
3. 不破坏现有自然日快照。

缺点：

1. 需要新增表、任务、DAO、服务和统计读取逻辑。
2. 历史业务周需要补跑。

#### 方案 C：新增小时级快照再聚合

不推荐作为第一阶段。

思路：

1. 按小时冻结统计。
2. 业务周统计时聚合小时快照。

优点：

1. 支持任意小时边界。
2. 后续支持更多自定义时间窗口。

缺点：

1. 数据量明显增加。
2. 指标如周期末存量、平均耗时、去重计数更复杂。
3. 当前需求只是业务周，不需要先上小时快照。

推荐取舍：

1. 第一阶段：实现默认时间配置和实时业务周分桶；快照业务周先给明确提示。
2. 第二阶段：如果周报必须按周四 18:00 稳定冻结，新增业务周期快照表和任务。

### 6. 相似工单系统详情独立页面

目标：

1. 点击相似工单“系统详情”只打开独立详情页。
2. 不加载工单列表、不初始化列表表格、不加载导入/列设置/列表筛选等列表页能力。

推荐设计：

1. 抽出详情组件：
   - `web/src/views/ticket/components/TicketDetailView.vue`
   - 或 `web/src/views/ticket/components/TicketDetailPanel.vue`
2. 工单列表页复用该详情组件展示弹窗。
3. 新增独立详情页：
   - `web/src/views/ticket/detail/index.vue`
   - 路由 `#/ticket/detail/:ticketId` 指向该页面。
4. 独立详情页职责：
   - 根据 route 参数读取工单详情。
   - 展示详情内容。
   - 按需加载日志拉取、评论、历史、AI 任务。
   - 不调用 `useTicketList`。
   - 不触发 `getList`。
5. 关闭/返回逻辑：
   - 如果独立页由新窗口打开，提供“关闭页面”或“返回上一页”。
   - 不自动跳转到 `/ticket/ticket`，避免用户认为打开了列表页。

## 分阶段实施计划

### 第一阶段：低风险体验修复

1. 统计页默认时间配置：
   - 支持 `rolling_days` 和 `business_week`。
   - 默认文案区分“最近 7 天”和“当前业务周”。
   - 重置恢复配置默认时间。
2. 统计页趋势明细列配置：
   - 新增 `ticket_statistics_detail_columns` 用户配置。
   - 默认展示当前全部列。
3. 独立详情页：
   - 抽出详情组件。
   - 路由指向独立详情页。
   - 相似工单“系统详情”打开独立页。

### 第二阶段：相似工单查询优化

1. 新增相似查询服务。
2. 详情页相似查询使用当前工单已保存向量。
3. 向量缺失或过期时，详情页同步刷新当前工单向量后再查询相似工单。
4. 数据变化入口继续自动刷新向量。
5. 补充单元测试覆盖：
   - 缓存向量命中不调用外部接口。
   - 内容 hash 变化后编辑入口会刷新。
   - 详情查询缺失向量时不调用外部接口。
   - Qdrant 查询使用缓存向量。

### 第三阶段：版本治理

1. 新增版本批量维护接口和页面操作。
2. 新增版本统计接口和页面。
3. 按 `affected_version/fixed_version/released_version` 支持明细下钻。
4. 需要正式周报时新增版本维度快照。

### 第四阶段：业务周快照

触发条件：

1. 周报必须按业务周起点冻结。
2. 用户明确要求快照口径下按周四 18:00 统计。

实施内容：

1. 新增 `ticket_statistics_period_snapshot`。
2. 新增业务周快照任务。
3. 统计页快照口径按业务周期读取。
4. 支持历史业务周补跑。

## 验证计划

### 后端

1. `cd server && uv run ruff check .`
2. 相似工单新增测试：
   - 详情相似查询复用 `embedding_record`。
   - 查询链路不调用 `_embed_text_openai_compatible`。
   - 编辑后内容变更触发向量刷新。
3. 统计时间工具测试：
   - 周四 18:00 前后的业务周起点计算。
   - `current` 和 `previous_completed` 窗口计算。
   - 滚动 N 天文案和时间边界。
4. 版本治理测试：
   - 批量发版写入版本字段。
   - 发版事件幂等写入。
   - 验证时间不误覆盖。

### 前端

1. `cd web && npm run build:prod`
2. 统计页：
   - 首次进入按配置显示默认时间范围。
   - 重置恢复默认范围。
   - 趋势明细列配置保存后刷新仍生效。
   - `rolling_days` 模式显示“最近 N 天”，不显示“最近一周”。
3. 独立详情页：
   - 相似工单“系统详情”打开后不出现工单列表。
   - 浏览器 Network 不请求列表接口。
   - 详情、日志、评论、历史仍可按需加载。

## 风险

1. 当前自然日快照不能精确支撑周四 18:00 业务周，这是数据模型边界，不应通过前端文案掩盖。
2. 如果详情页相似查询发现当前工单向量过期但不立即外部向量化，短时间内可能显示暂无相似工单；需要用状态提示或后台补偿任务改善体验。
3. 版本统计如果按 Ticket 统计，会把重复反馈也计入；如果要统计真实问题数，应优先按 `ticket_issue` 去重。
4. 独立详情页抽组件会触碰当前较大的 `ticket/index.vue`，实现时必须小步拆分，先迁移详情展示，再迁移详情动作，避免顺手重构列表逻辑。

## 后续实现入口

建议优先关注以下文件：

1. `server/modules/ticket/service/ai/ticket_embedding_service.py`
2. `server/modules/ticket/service/ai/ticket_similarity_query_service.py`
3. `server/modules/ticket/service/core/ticket_service.py`
4. `server/modules/ticket/service/core/ticket_release_service.py`
5. `server/modules/ticket/service/stats/ticket_processing_stats_service.py`
6. `server/modules/ticket/service/stats/ticket_statistics_snapshot_service.py`
7. `server/modules/ticket/util/ticket_statistics_time_util.py`
8. `web/src/views/ticket/statistics/index.vue`
9. `web/src/views/ticket/detail/index.vue`
10. `web/src/views/ticket/components/TicketDetailView.vue`
11. `web/src/views/ticket/hooks/useTicketList.js`
12. `web/src/router/index.js`
