# 2026-07-05 相似工单手动重建改用 ticketNo

## 背景

相似工单配置页的“手动重建”原来要求输入系统内部 `ticketId`。业务排查时用户手里通常是外部工单号 `ticketNo`，用内部 ID 操作容易输错，也不符合工单同步链路的主业务标识。

## 本次改动

1. 前端 `ticket/similarityConfig/index` 的重建范围从“指定工单ID”改为“指定工单号”。
2. `POST /ticket/similarity/rebuild` 新增 `ticketNos` 入参，多个工单号由前端按逗号、空格或换行拆分。
3. 后端 `TicketEmbeddingRebuildRequestModel` 继续兼容旧 `ticketIds`，但新页面只提交 `ticketNos`。
4. `TicketEmbeddingService.resolve_ticket_ids_for_rebuild` 会先按 `ticketNos` 查询有效工单，再把结果转换为系统 `ticket_id` 复用现有重建逻辑。
5. 当指定的 `ticketNo` 全部不存在时，DAO 返回 0 条并停止处理，避免误回退成全量重建。
6. 同步执行结果会返回 `missingTicketNos`，后台执行完成日志也会记录缺失工单号，便于判断为什么未处理。

## 接口示例

```json
{
  "allTickets": false,
  "ticketNos": ["INC202607050001", "INC202607050002"],
  "pageSize": 100,
  "provider": "qdrant",
  "includeQdrant": true,
  "runInBackground": false
}
```

旧 `ticketIds` 仍保留兼容，但手动页面不再使用。

## 本地 hash 与真实 Embedding 差异

差异较大：

- `local_hash` 是确定性哈希向量，优点是无需外部服务、速度快、成本低，适合开发、兜底和粗略关键词相似。
- 真实 Embedding 会根据语义把“现象不同但根因相同”“描述用词不同但业务含义接近”的工单拉近，更适合历史相似案例召回。
- `local_hash` 对同义词、跨语言、描述顺序和上下文理解弱，容易更像“文本指纹/词面相近”。
- 真实 Embedding 依赖模型、维度、网络和 Qdrant collection 配置，成本和稳定性要求更高。

当前建议：开发和兜底保留 `local_hash`；生产要做可靠相似案例推荐时，配置 `openai_compatible` Embedding + Qdrant，并在模型或参与字段变化后执行一次重建。

## 验证记录

- 2026-07-05 07:56:36 +08:00：完成字段契约和页面改造。
- 待执行：后端 `uv run ruff check .` 和前端 `npm run build:prod`。

