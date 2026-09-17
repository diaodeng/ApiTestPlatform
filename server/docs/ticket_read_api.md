# 工单轻量读取接口

工单详情页可按需使用以下只读接口，避免首次打开页面加载完整消息、快照和相似度数据。

## 接口

- `GET /ticket/{ticket_id}/summary`：返回工单基础信息、项目/模块业务码、四类版本展示信息、Issue 摘要、最新日志/AI 摘要、当前 AI 提示词层摘要，以及当前工单自身的相似处理案例摘要 `similarityCase`。提示词层包含项目默认提示词、按 `module_code` 命中的模块通用说明、当前项目模块说明，以及组合后的 `defaultPromptText/hasDefaultPrompt`；不读取消息、快照或相似工单。
  - `similarityCase` 为当前工单在 `ticket_similarity_case` 表中的案例摘要（`caseStatus/caseRevision/reusable`、根因与方案等摘要字段、确认与驳回人信息、案例向量索引状态 `lastIndexStatus/lastIndexError`）。工单尚未形成案例时返回 `{ caseStatus: "none" }`，该字段只读，不透出案例内部主键。
- `GET /ticket/{ticket_id}/similar-tickets?limit=5`：查询相似工单。`limit` 默认 5，范围限制为 1-100。响应 `data` 为 `{ status, message, items }`，`items` 仅包含工单编号、标题、状态、项目/模块、分类、优先级、严重等级、根因/解决方式、关闭结果和相似度分数等摘要字段，不包含描述和扩展数据。
  - 结果缓存：`status != error` 的查询结果按 `工单ID + limit + 相似度配置指纹` 缓存到 Redis（键前缀 `ticket:similar-result`，TTL 5 分钟；`CACHE_BACKEND=memory` 时降级为进程内缓存）。缓存命中时不执行向量扫描；`error` 结果不缓存。工单向量刷新（`vectorize_ticket_for_scene` 各场景）和相似案例状态变更后主动失效该工单的缓存。Redis 不可用时自动降级为直查，不影响接口可用性。
- `GET /ticket/{ticket_id}/messages/page?limit=20`：按需读取最近协同消息。`limit` 默认 20，最大 100。响应 `data` 为 `{ items, limit, hasMore }`。
- `GET /ticket/{ticket_id}/snapshots/page?limit=10`：按需读取最近 ACR 快照。`limit` 默认 10，最大 100。响应 `data` 为 `{ items, limit, hasMore }`，快照按版本倒序返回。
- `GET /ticket/{ticket_id}/edit-detail`：工单编辑回填专用轻量接口。只返回编辑表单需要的字段：工单本体、项目/模块业务码、四类版本 ID 与展示名、处理人、问题分类、工单类型、`tags`、`categoryName`、`problemPatternVerified`、`extraData`（前端从中还原日志拉取/自动翻译配置）、`originalDescription`/`aiTranslation`，以及最近一次日志拉取摘要。不读取消息、快照、相似工单、AI 提示词分层和 Token 统计。工单列表编辑弹窗与日志拉取管理页预填使用该接口；全部主键与关联 ID 以字符串返回，更新时由 `TicketUpdateModel` 解析回整数。

所有接口使用登录态和现有工单查询/消息查询权限。不存在的工单沿用 `ResponseUtil.failure` 返回“工单不存在”。工单、Issue、消息和快照的 BIGINT 主键以字符串返回，避免浏览器整数精度丢失。

原有 `GET /ticket/{ticket_id}` 完整详情接口和 `GET /ticket/{ticket_id}/messages` 契约保持不变。
