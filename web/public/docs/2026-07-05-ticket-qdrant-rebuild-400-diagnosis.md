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
7. 查询链路不会因为该开关删除 collection；查询失败会直接返回错误，不再回退本地向量。
8. OpenAI 兼容 Embedding 请求默认不下发 `dimensions`，只用 `embedding.dimension` 校验返回向量长度；如模型支持维度裁剪，可在 `embedding.requestParams` 中显式配置 `{"dimensions": 1024}`。
9. 同步 Qdrant 时，外部 Embedding 失败会直接让本条重建失败，不再回退本地 hash 写入 Qdrant，避免 collection 在真实模型维度和本地 hash 维度之间反复重建。
10. collection 重建遇到并发 409 时，会再次读取 collection 详情；若维度已经符合当前向量维度，则视为成功。
11. 重建过程新增关键日志：开始配置、批次进度、单工单文本长度、Embedding 请求维度、返回维度、Qdrant collection 维度、执行或跳过原因。
12. 批量重建中如果外部 Embedding 调用失败，会记录 `abortReason` 并停止后续工单的外部接口请求，避免本地环境或上游异常时继续消耗 token。
13. 手动重建新增 `forceRebuild`：默认关闭并按幂等跳过已有向量，开启后才强制重新调用外部 Embedding。
14. 幂等判断会比较模型、版本、配置维度、已存向量长度和内容哈希；内容哈希包含配置的向量化字段列表和最终文本，字段配置变化会触发重新生成。
15. 相似查询和向量入库改为严格 Provider：`local_hash` 只用数据库 `embedding_record` 的本地 hash，`embedding` 只用外部 Embedding 写入/查询数据库 `embedding_record`，`qdrant` 只用外部 Embedding + Qdrant；失败不做降级。
16. 配置页新增 Qdrant collection 列表查询，显示 collection 名称、维度、距离算法和状态；配置维度与 collection 维度不一致时给出提示。

## 常见原因

- `embedding.dimension` 配置仍是本地 hash 的 128，但真实 Embedding 模型返回 768/1024/1536 等维度。
- Qdrant `ticket_similarity` collection 之前按旧维度创建，后来更换了 Embedding 模型。
- 历史版本外部 Embedding 接口失败后回退本地 hash，实际写入维度变回配置维度或 128，和既有 collection 不一致；当前严格模式已取消该回退。
- 历史版本多个重建任务并发执行时，一个任务按真实 Embedding 维度重建，另一个任务因外部接口失败按 hash 维度重建，会导致 collection 维度来回切换；当前严格模式下外部异常会失败并熔断。
- 日志中的 `vectorDimension=2560` 来源是本次代码拿到的实际向量长度，通常来自外部 Embedding 接口返回值或旧 collection 的既有维度；若页面配置是 1024，则应检查外部接口实际返回维度，或确认是否需要在 `embedding.requestParams` 中显式配置 `dimensions=1024`。

## 请求粒度

当前重建不是把多个工单合并成一次 Embedding 请求，而是一条工单一次外部 Embedding 请求。

批量重建看起来 token 消耗更高，通常是因为：

- 批量会连续处理多条工单，总 token 为多次请求累加。
- 每条工单的向量化文本包含标题、描述、AI 摘要、根因、解决方案和 RCA，某些历史工单文本更长。
- 开启 Qdrant 同步时，外部 Embedding 失败会停止后续请求，不再继续消耗后续工单 token。

## 幂等与强制重建

- 手动重建默认不强制：若本地 `embedding_record` 已经有同一 `model/version/dimension/contentHash` 的向量，会记录“跳过外部Embedding请求”，结果中的 `idempotentSkipped` 会增加。
- 如果当前 `provider=qdrant` 且命中幂等，服务会用本地已存向量写入 Qdrant，结果中的 `qdrantSyncedFromCache` 会增加；这个过程不请求外部 Embedding。
- 页面开启“强制重建”后，服务忽略已有向量并重新请求外部 Embedding，适用于确认上游模型内部升级、旧向量质量不可信或需要覆盖历史数据的场景。
- 自动刷新场景也复用同一幂等逻辑；相似工单配置未启用或场景开关关闭时，日志会记录跳过原因。

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
- 2026-07-05 10:12:00 +08:00：禁止 Qdrant 同步时回退本地 hash，Embedding 请求校验返回维度。
- 2026-07-06 11:15:00 +08:00：Embedding 请求默认不再补充 `dimensions`，改由 `embedding.requestParams` 自定义透传。
- 2026-07-05 10:20:00 +08:00：新增批量重建过程日志与外部 Embedding 失败熔断，明确一工单一次 Embedding 请求。
- 2026-07-05 10:55:00 +08:00：新增向量重建幂等跳过和强制重建开关，执行 `uv run python -m unittest tests.test_ticket_embedding_service` 通过 12 个测试。
- 2026-07-05 10:55:00 +08:00：执行 `uv run ruff check modules\ticket\service\ai\ticket_embedding_service.py tests\test_ticket_embedding_service.py`，通过。
- 2026-07-05 10:53:00 +08:00：执行 `npm run build:prod`，通过；仅保留既有 Vite 大 chunk、eval 和 `/config.js` 非 module 警告。
- 2026-07-05 14:17:38 +08:00：严格 Provider 模式和 Qdrant collection 维度预览改造后，执行 `uv run python -m unittest tests.test_ticket_embedding_service`，通过 14 个测试。
- 2026-07-05 14:17:38 +08:00：执行 `uv run ruff check modules\ticket\service\ai\ticket_embedding_service.py modules\ticket\controller\ticket_config_controller.py tests\test_ticket_embedding_service.py`，通过。
- 2026-07-05 14:20:00 +08:00：执行 `npm run build:prod`，通过；仅保留既有 Vite 大 chunk、eval 和 `/config.js` 非 module 警告。
