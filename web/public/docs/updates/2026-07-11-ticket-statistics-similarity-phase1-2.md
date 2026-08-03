# 2026-07-11 工单统计与相似工单第一、二阶段实现记录

## 结论

本记录描述第一、二阶段当时的落地范围，当时未实现版本治理、版本统计和业务周快照新表。业务周快照新表已在 `2026-07-11-ticket-business-week-period-snapshot.md` 中补齐。

已完成：

1. 统计页默认时间配置：新增系统参数 `ticket.statistics.time.config` 和接口 `GET /ticket/statistics/time-config`。
2. 实时业务周趋势：`GET /ticket/statistics/trend` 新增 `weekBucketMode=calendar_week|business_week`。
3. 快照业务周限制提示：本阶段当时快照口径选择业务周会返回 `warnings`；后续已改为读取 `ticket_statistics_period_snapshot` 精确统计。
4. 趋势明细列配置：新增用户配置 `ticket/ticket_statistics_detail_columns`，`bucket` 为必选列。
5. 详情页相似工单优先复用当前工单已保存向量：向量缺失或过期时同步刷新向量后再查询。
6. 独立详情页：`#/ticket/detail/:ticketId` 改为加载独立页面，不再复用工单列表页组件。
7. 2026-07-12 修正：`TicketDetail` 路由从 `Layout` 子路由提升为顶层纯页面，打开相似工单“系统详情”时不再显示左侧菜单、顶部导航或标签栏；纯详情页继续保留工单描述和 AI 翻译的收起/展开能力。

## 后端变更

### 统计默认时间

- 新增 `server/modules/ticket/util/ticket_statistics_time_util.py`。
- 默认配置：

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

接口 `GET /ticket/statistics/time-config` 返回：

- `config`
- `defaultRange`
- `rangeLabel`
- `snapshotBusinessWeekSupported=true`（后续已由业务周周期快照补齐）

### 趋势业务周

- `TicketStatisticsQueryModel` 新增 `week_bucket_mode`。
- `TicketProcessingStatsService.get_statistics_trend` 根据 `weekBucketMode` 选择自然周或业务周。
- `TicketDao.get_statistics_trend` 同步支持业务周分桶，保证整体趋势、问题性质趋势、Top 模块和 Top 细分问题口径一致。
- `statisticsMode=snapshot && weekBucketMode=business_week` 后续已改为读取业务周周期快照，不再返回自然日快照限制 warning。

### 相似工单

- `TicketEmbeddingService` 新增：
  - `get_ticket_embedding_context`
  - `search_tickets_by_vector`
  - `search_embedding_records_by_vector`
  - `search_qdrant_by_vector`
- 新增 `TicketSimilarityQueryService.search_similar_tickets_by_ticket`，负责按当前工单优先读取缓存向量并查询相似工单。
- `TicketService.get_messages_services` 不再拼接文本调用 `search_tickets`，只调用相似查询子服务组装详情响应。
- 当前工单向量缺失或过期时，详情接口会按当前 Provider 配置调用 `vectorize_ticket` 刷新向量，再用刷新后的向量查询库内向量或 Qdrant。
- 当前工单向量刷新成功时，详情接口返回：
  - `similarEmbeddingStatus=ready`
  - `similarEmbeddingMessage=当前工单向量已刷新后完成相似工单查询。`
- 相似检索关闭或刷新失败时，详情接口返回：
  - `similarEmbeddingStatus=disabled/error`
  - `similarEmbeddingMessage`
  - `similarTickets=[]`

## 前端变更

### 统计页

- `web/src/views/ticket/statistics/index.vue` 首次进入先读取 `GET /ticket/statistics/time-config`。
- “重置”恢复系统参数默认时间范围，不再清空时间。
- 时间选择器改为日期时间范围，业务周默认范围保留周四 18:00 边界。
- 周粒度下显示“自然周 / 业务周”分桶切换。
- 显示配置弹窗新增“趋势明细列”区域。
- 新增用户配置：
  - `configType=ticket`
  - `configKey=ticket_statistics_detail_columns`

### 独立详情页

- 新增 `web/src/views/ticket/components/TicketDetailView.vue`。
- 新增 `web/src/views/ticket/detail/index.vue`。
- 路由 `TicketDetail` 指向独立详情页；2026-07-12 起该路由直接挂在顶层 `/ticket/detail/:ticketId`，不再作为 `/ticket` 的 `Layout` 子路由。
- 独立详情页只调用详情、评论、时间线等详情相关接口，不调用 `useTicketList`，不会请求 `/ticket/list`。
- `TicketDetailView` 内置描述和 AI 翻译的展开状态，默认展开；用户收起后保留一行预览，切换到其他工单时恢复展开。

## 未实施范围

- 业务周快照表和快照口径下周四 18:00 精确业务周统计已在后续实现记录中补齐。
- 未实现版本批量维护。
- 未实现版本统计页面或 API。

## 验证

- 新增时间工具单测覆盖周四 18:00 前后、current、previous_completed、rolling_days。
- 新增相似查询单测覆盖缓存向量查询不调用外部 Embedding、向量缺失时详情查询会刷新向量、Qdrant 查询使用给定缓存向量，以及 `TicketSimilarityQueryService` 入口复用缓存向量上下文。
- 需执行：
  - `cd server && uv run ruff check modules/ticket tests/test_ticket_embedding_service.py tests/test_ticket_statistics_time_util.py`
  - `cd web && npm run build:prod`
