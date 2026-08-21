# 工单轻量读取接口

工单详情页可按需使用以下只读接口，避免首次打开页面加载完整消息、快照和相似度数据。

## 接口

- `GET /ticket/{ticket_id}/summary`：返回工单基础信息、项目/模块业务码、四类版本展示信息、Issue 摘要及最新日志/AI 摘要。不读取消息、快照、相似工单或提示词层。
- `GET /ticket/{ticket_id}/similar-tickets?limit=5`：查询相似工单。`limit` 默认 5，范围限制为 1-100。响应 `data` 为 `{ status, message, items }`，`items` 仅包含工单编号、标题、状态、项目/模块、分类、优先级、严重等级、根因/解决方式、关闭结果和相似度分数等摘要字段，不包含描述和扩展数据。
- `GET /ticket/{ticket_id}/messages/page?limit=20`：按需读取最近协同消息。`limit` 默认 20，最大 100。响应 `data` 为 `{ items, limit, hasMore }`。
- `GET /ticket/{ticket_id}/snapshots/page?limit=10`：按需读取最近 ACR 快照。`limit` 默认 10，最大 100。响应 `data` 为 `{ items, limit, hasMore }`，快照按版本倒序返回。

所有接口使用登录态和现有工单查询/消息查询权限。不存在的工单沿用 `ResponseUtil.failure` 返回“工单不存在”。工单、Issue、消息和快照的 BIGINT 主键以字符串返回，避免浏览器整数精度丢失。

原有 `GET /ticket/{ticket_id}` 完整详情接口和 `GET /ticket/{ticket_id}/messages` 契约保持不变。
