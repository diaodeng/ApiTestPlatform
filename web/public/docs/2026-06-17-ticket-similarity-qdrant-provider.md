# 工单相似度检索配置化与 Qdrant Provider

## 背景

原相似工单检索使用本地哈希向量，并把关键词命中直接合并为 `score=1.0`。该方式不理解标题和描述的真实语义，且容易因为字段包含同一关键词而误判为高相似工单。

## 本次改动

1. `TicketEmbeddingService` 改为配置化相似检索适配层，严格按 `provider` 使用 `local_hash`、`embedding` 或 `qdrant`，失败不再降级。
2. 新增 `qdrant` Provider，支持通过 HTTP API 写入和查询 Qdrant collection。
3. 新增 `embedding` Provider，使用兼容 OpenAI `/v1/embeddings` 的外部向量并把向量存入数据库 `embedding_record`。
4. 相似工单文本范围扩展为标题、描述、AI 摘要、最终根因、解决方案、RCA、模块、分类和标签。
5. 查询结果只来自当前 Provider 的向量召回，不再混入关键词命中加分，避免“包含同一字段文案”导致相似工单统计失真。
6. 新增批量重建接口，支持把历史工单按配置字段重新写入当前 Provider：`local_hash` 和 `embedding` 写数据库 `embedding_record`，`qdrant` 写 Qdrant。
7. 新增相似工单配置页面 `ticket/similarityConfig/index`，可视化维护 Provider、Embedding、Qdrant、场景触发开关，并提供手动重建按钮。
8. 新增 `sceneTriggers` 场景开关，外部同步、远端拉取、手动新增、手动编辑、Excel 导入和关闭知识沉淀链路都会按配置决定是否刷新向量。
9. 向量生成新增幂等判断：同一工单在模型、版本、配置维度、参与字段和最终向量文本都未变化时，直接复用 `embedding_record`，不再调用外部 Embedding 接口。

## 系统参数

参数键：`ticket.similarity.config`

默认配置：

```json
{
  "enabled": true,
  "provider": "local_hash",
  "topK": 20,
  "threshold": 0.05,
  "keywordWeight": 0.15,
  "vectorWeight": 0.85,
  "fields": [
    "ticketNo",
    "title",
    "description",
    "aiSummary",
    "rootCause",
    "solution",
    "rca",
    "moduleName",
    "categoryName",
    "tags"
  ],
  "embedding": {
    "provider": "local_hash",
    "model": "local-hash",
    "version": "v1",
    "dimension": 128,
    "endpoint": "",
    "apiKey": "",
    "timeoutSeconds": 15
  },
  "qdrant": {
    "url": "http://127.0.0.1:6333",
    "apiKey": "",
    "collection": "ticket_similarity",
    "distance": "Cosine",
    "timeoutSeconds": 15,
    "createCollection": true,
    "recreateCollectionOnDimensionMismatch": false
  },
  "sceneTriggers": {
    "externalSync": true,
    "remotePull": true,
    "manualCreate": true,
    "manualUpdate": true,
    "import": true,
    "closeKnowledge": true
  }
}
```

Provider 说明：

- `provider=local_hash`：生成本地 hash 向量，存储和查询都使用数据库表 `embedding_record`，不请求外部 Embedding，也不请求 Qdrant。
- `provider=embedding`：调用外部 Embedding 生成向量，存储和查询都使用数据库表 `embedding_record`；外部接口失败直接报错。
- `provider=qdrant`：调用外部 Embedding 生成查询/入库向量，存储和查询都使用 Qdrant；外部 Embedding 或 Qdrant 失败直接报错。

`provider=embedding` 与 `provider=qdrant` 的语义召回质量主要取决于同一个外部 Embedding 模型，理论相似度效果基本一致；差异主要在存储和检索能力。`embedding` 把向量存在数据库 JSON 字段并由服务端逐条计算余弦相似度，适合数据量较小或简化部署；`qdrant` 把向量交给专业向量库索引，适合数据量较大、查询频繁或需要向量库能力的生产场景。

启用 Qdrant 时至少调整：

- `provider`: `qdrant`
- `embedding.provider`: 推荐使用 `openai_compatible`
- `embedding.endpoint`: 兼容 OpenAI Embedding 的接口地址
- `embedding.model`: 实际 Embedding 模型名
- `embedding.dimension`: 实际模型维度，会作为 Embedding 请求 `dimensions` 参数下发，且必须与 Qdrant collection 一致
- `qdrant.url`: Qdrant 服务地址
- `qdrant.collection`: collection 名称

## 可视化入口

菜单：`工单管理 / 相似工单配置`

页面能力：

- 保存基础检索配置：启用状态、Provider、召回数量、阈值、关键词权重、向量权重、参与向量化字段。
- 保存 Embedding 配置：页面按检索 Provider 联动展示。`local_hash` 只显示本地哈希和维度；`embedding/qdrant` 显示兼容 OpenAI Embedding 的 endpoint、model、dimension、apiKey、timeout。
- 保存 Qdrant 配置：仅 `provider=qdrant` 时展示 url、apiKey、collection、distance、timeout、是否自动创建 collection、维度不一致时是否删除并重建 collection。切换到其他 Provider 时隐藏但不清空原 Qdrant 配置。
- 查询 Qdrant collection 列表：页面会通过 `POST /ticket/similarity/qdrant/collections` 显示 collection 名称、维度、距离算法和状态；当前配置维度与所选 collection 维度不一致时会提示并阻止保存。
- 保存场景触发开关：`externalSync`、`remotePull`、`manualCreate`、`manualUpdate`、`import`、`closeKnowledge`。
- 手动重建历史向量：支持全部有效工单或指定工单号 `ticketNo`，支持同步/后台执行。手动重建 Provider 选项跟随当前检索 Provider 收敛，只允许“跟随配置”或当前 Provider，避免选择当前页面配置不支持的组合；是否写 Qdrant 只由最终 Provider 是否为 `qdrant` 决定。

## 接口

### 获取/初始化配置

`GET /ticket/similarity/config`

读取当前配置；如果系统参数不存在，会写入默认配置。

### 保存配置

`PUT /ticket/similarity/config`

保存相似工单检索配置，包含 Provider、Embedding、Qdrant 和 `sceneTriggers`。接口会规范化数值范围和 Provider 值；当 `provider=qdrant` 且目标 collection 已存在时，会校验 collection 维度与 `embedding.dimension` 一致后再写入系统参数 `ticket.similarity.config`。

### 重建向量

`POST /ticket/similarity/rebuild`

请求示例：

```json
{
  "allTickets": true,
  "pageSize": 100,
  "provider": "qdrant",
  "runInBackground": true,
  "forceRebuild": false
}
```

指定工单重建：

```json
{
  "ticketNos": ["INC202607050001", "INC202607050002"],
  "allTickets": false,
  "runInBackground": false,
  "forceRebuild": false
}
```

### 查询 Qdrant Collection

`POST /ticket/similarity/qdrant/collections`

请求示例：

```json
{
  "embedding": {
    "dimension": 1024
  },
  "qdrant": {
    "url": "http://127.0.0.1:6333",
    "apiKey": "",
    "timeoutSeconds": 15
  }
}
```

## 自动刷新场景

`TicketEmbeddingService.vectorize_ticket_for_scene` / `vectorize_tickets_for_scene` 会先读取 `ticket.similarity.config.sceneTriggers`，关闭的场景不会刷新向量。

## 本地 hash、Qdrant 与幂等

- 本地 hash 向量可以写入 Qdrant，技术上可行；但当前严格模式下 `provider=local_hash` 不写 Qdrant，`provider=qdrant` 必须使用外部 Embedding。
- 真实 Embedding 更适合“描述不同但问题相同”的相似工单召回；本地 hash 更容易受共同关键词、字段模板和短词影响。
- 搜索是否使用 Qdrant 由 `ticket.similarity.config.provider` 决定：`provider=qdrant` 时只查 Qdrant，失败直接报错；`provider=local_hash` 和 `provider=embedding` 都只查数据库 `embedding_record`。
- 不使用 Qdrant 时，向量数据存储在数据库表 `embedding_record.embedding` JSON 字段中，不存本地文件。
- 手动重建默认 `forceRebuild=false`，会按幂等判断跳过外部 Embedding 请求；页面开启“强制重建”后才会忽略已有向量并重新请求外部接口。
- 幂等键由 `object_type/object_id + embedding.model + embedding.version + embedding.dimension + content_hash` 共同决定。`content_hash` 包含当前配置的 `fields` 列表和最终参与向量化的文本，因此调整向量化字段或工单内容变化都会触发重新生成。
- 幂等命中且当前 `provider=qdrant` 时，会复用本地已保存向量写入 Qdrant，不再调用外部 Embedding 接口。

## 重建日志与熔断

- 当前重建粒度是一条工单一次 Embedding 请求，不会把多条工单合并成一个外部请求。
- 日志会记录重建配置、批次进度、单工单文本字符数、请求维度、返回维度、Qdrant collection 维度、幂等跳过、场景开关跳过和 Qdrant 复用写入原因。
- 外部 Embedding 失败时，本次批量重建会停止后续外部请求，并在结果中返回 `abortReason` 和 `skipped`。
- 若页面配置维度与返回维度不一致，服务会报 `Embedding接口返回维度与配置不一致`，不会写入 Qdrant。

| 场景键 | 触发链路 | 说明 |
|---|---|---|
| `externalSync` | 外部系统 `POST /ticket/sync/external` 延后后处理 | 公网外部推送入库或更新后刷新 |
| `remotePull` | 内网远端拉取公网 pending 后延后后处理 | 内网消费远端工单落库后刷新 |
| `manualCreate` | 工单列表手动新增 | 新增成功并完成自动分类后刷新 |
| `manualUpdate` | 工单列表手动编辑 | 基础信息保存后刷新 |
| `import` | Excel 导入 | 本批成功导入工单批量刷新 |
| `closeKnowledge` | 关闭工单自动知识沉淀 | 生成知识库案例后刷新 |

## 推荐 Qdrant 部署

本地或单机环境可先使用 Docker：

```bash
docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

生产环境建议：

- 为 Qdrant 配置 API Key，并写入 `qdrant.apiKey`。
- collection 名称按环境区分，例如 `ticket_similarity_dev`、`ticket_similarity_prod`。
- Embedding 模型维度变更时，优先新建 collection；若确认旧 Qdrant 数据可丢弃，可开启 `recreateCollectionOnDimensionMismatch` 后执行全量重建。

## 风险与回滚

- 如果 Qdrant 不可用，`provider=qdrant` 的查询和入库会直接失败，不再回退本地哈希。
- 如果 Embedding 服务不可用，`provider=embedding` 和 `provider=qdrant` 会直接失败；`provider=local_hash` 不调用外部服务。
- `recreateCollectionOnDimensionMismatch` 只在写入/重建链路生效，开启后会删除旧 collection 的全部点；建议配合全部有效工单重建使用。
- 回滚只需把 `ticket.similarity.config.provider` 改回 `local_hash`，不需要删除 Qdrant 数据。
