# 工单相似度检索配置化与 Qdrant Provider

## 背景

原相似工单检索使用本地哈希向量，并把关键词命中直接合并为 `score=1.0`。该方式不理解标题和描述的真实语义，且容易因为字段包含同一关键词而误判为高相似工单。

## 本次改动

1. `TicketEmbeddingService` 改为配置化相似检索适配层，默认保留 `local_hash` 本地哈希向量兜底。
2. 新增 `qdrant` Provider，支持通过 HTTP API 写入和查询 Qdrant collection。
3. 新增兼容 OpenAI `/v1/embeddings` 的 Embedding 配置，默认仍使用本地哈希向量；接入真实 Embedding 服务后只需修改系统参数。
4. 相似工单文本范围扩展为标题、描述、AI 摘要、最终根因、解决方案、RCA、模块、分类和标签。
5. 关键词命中不再直接给满分，改为弱加分，降低误统计。
6. 新增批量重建接口，支持把历史工单按“标题 + 描述 + AI 摘要 + RCA”重新写入本地 `embedding_record`，并可同步写入 Qdrant。
7. 新增相似工单配置页面 `ticket/similarityConfig/index`，可视化维护 Provider、Embedding、Qdrant、场景触发开关，并提供手动重建按钮。
8. 新增 `sceneTriggers` 场景开关，外部同步、远端拉取、手动新增、手动编辑、Excel 导入和关闭知识沉淀链路都会按配置决定是否刷新向量。

## 系统参数

参数键：`ticket.similarity.config`

默认配置：

```json
{
  "enabled": true,
  "provider": "local_hash",
  "fallbackProvider": "local_hash",
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

- 保存基础检索配置：启用状态、Provider、兜底 Provider、召回数量、阈值、关键词权重、向量权重、参与向量化字段。
- 保存 Embedding 配置：`local_hash` 或兼容 OpenAI Embedding 的 endpoint、model、dimension、apiKey、timeout。
- 保存 Qdrant 配置：url、apiKey、collection、distance、timeout、是否自动创建 collection、维度不一致时是否删除并重建 collection。
- 保存场景触发开关：`externalSync`、`remotePull`、`manualCreate`、`manualUpdate`、`import`、`closeKnowledge`。
- 手动重建历史向量：支持全部有效工单或指定工单号 `ticketNo`，支持同步/后台执行，支持强制指定 Provider 和是否同步 Qdrant。

## 接口

### 获取/初始化配置

`GET /ticket/similarity/config`

读取当前配置；如果系统参数不存在，会写入默认配置。

### 保存配置

`PUT /ticket/similarity/config`

保存相似工单检索配置，包含 Provider、Embedding、Qdrant 和 `sceneTriggers`。接口会规范化数值范围和 Provider 值，并写入系统参数 `ticket.similarity.config`。

### 重建向量

`POST /ticket/similarity/rebuild`

请求示例：

```json
{
  "allTickets": true,
  "pageSize": 100,
  "provider": "qdrant",
  "includeQdrant": true,
  "runInBackground": true
}
```

指定工单重建：

```json
{
  "ticketNos": ["INC202607050001", "INC202607050002"],
  "allTickets": false,
  "includeQdrant": true,
  "runInBackground": false
}
```

## 自动刷新场景

`TicketEmbeddingService.vectorize_ticket_for_scene` / `vectorize_tickets_for_scene` 会先读取 `ticket.similarity.config.sceneTriggers`，关闭的场景不会刷新向量。

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

- 如果 Qdrant 不可用，查询会记录警告并回退本地哈希检索。
- 如果 Embedding 服务不可用，纯本地检索仍可回退本地哈希向量；但同步 Qdrant 时会直接失败，不再用本地哈希向量写入 Qdrant。
- `recreateCollectionOnDimensionMismatch` 只在写入/重建链路生效，开启后会删除旧 collection 的全部点；建议配合全部有效工单重建使用。
- 回滚只需把 `ticket.similarity.config.provider` 改回 `local_hash`，不需要删除 Qdrant 数据。
