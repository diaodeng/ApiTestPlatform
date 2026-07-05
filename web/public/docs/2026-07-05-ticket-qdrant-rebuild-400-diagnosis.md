# 2026-07-05 工单向量重建 Qdrant 400 诊断增强

## 背景

手动重建指定工单向量时，Qdrant 写入接口返回 400：

```text
PUT /collections/ticket_similarity/points 400
工单向量重建失败: ticket_id=2024504473869312, ticket_no=INC00001699695
```

原实现直接调用 `response.raise_for_status()`，日志只能看到 `400 Client Error`，缺少 Qdrant 返回体，无法判断是向量维度、点 ID、payload 还是 collection 配置问题。

## 本次改动

1. `TicketEmbeddingService._ensure_qdrant_collection` 增加 `expected_dimension` 参数。
2. Qdrant collection 已存在时，读取 collection 详情里的向量维度并与本次实际向量维度比较。
3. 发现维度不一致时，在写入或查询前直接抛出清晰错误，提示检查 Embedding 模型、配置维度和既有 collection。
4. collection 不存在且允许自动创建时，优先使用本次实际向量维度创建 collection，避免配置维度和真实 Embedding 返回维度不一致。
5. 新增 `_raise_for_qdrant_status`，Qdrant 4xx/5xx 异常会携带响应体前 1000 字符，后续日志能看到服务端原始错误。
6. 新增 `qdrant.recreateCollectionOnDimensionMismatch` 开关，默认关闭；开启后仅在写入/重建链路维度不一致时删除旧 collection 并按当前向量维度重建。
7. 查询链路不会因为该开关删除 collection；查询失败仍会走本地向量回退，避免用户搜索时触发数据清理。

## 常见原因

- `embedding.dimension` 配置仍是本地 hash 的 128，但真实 Embedding 模型返回 768/1024/1536 等维度。
- Qdrant `ticket_similarity` collection 之前按旧维度创建，后来更换了 Embedding 模型。
- 外部 Embedding 接口失败后回退本地 hash，实际写入维度变回配置维度或 128，和既有 collection 不一致。

## 处理建议

1. 在相似工单配置页确认 `embedding.provider/model/dimension` 与实际 Embedding 服务一致。
2. 如果更换了模型或维度，建议配置新的 Qdrant collection 名称，例如 `ticket_similarity_1536`。
3. 保存配置后执行一次手动重建，确保本地 `embedding_record` 和 Qdrant 使用同一模型版本。
4. 若沿用旧 collection 且确认可丢弃旧 Qdrant 向量，可在页面开启“维度不一致时重建”，再执行手动重建。
5. 开启该开关后旧 collection 内所有点会被删除；重建范围应选择全部有效工单，避免只写入少量指定工单导致 Qdrant 索引不完整。

## 验证记录

- 2026-07-05 09:07:30 +08:00：执行 `uv run python -m unittest tests.test_ticket_embedding_service`，通过 3 个测试。
- 2026-07-05 09:07:30 +08:00：执行 `uv run ruff check modules\ticket\service\ai\ticket_embedding_service.py tests\test_ticket_embedding_service.py`，通过。
- 2026-07-05 09:18:00 +08:00：新增维度不一致时可配置重建 collection 的后端和页面开关。
