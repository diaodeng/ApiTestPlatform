# 2026-09-03 工单相似精确信号召回修复与相似结果 Redis 缓存

## 变更内容

### 1. 精确信号循环缩进缺陷修复（召回质量）

`TicketHybridSimilarityService.search_by_vector`（`server/modules/ticket/service/ai/ticket_hybrid_similarity_service.py`）中，精确信号候选扩展的 `for ticket_id in signal_hits` 缩进在 `for signal_type` 循环外，导致 `signal_hits` 每轮被覆盖，最终只消费最后一种信号类型（error_code）的命中，Trace ID / Request ID 命中的候选工单全部丢失。修复后将内层循环移入信号类型循环内，三类信号命中均进入候选池，再由重排阶段按信号一致加分（Trace ID 0.55 / Request ID 0.45 / 错误码 0.35）。

影响场景：措辞不同导致向量召回失败、但共享同一 Trace ID / Request ID（同一问题最硬证据）的工单，此前彻底无法进入相似结果。

### 2. 相似工单查询结果缓存（性能）

新增 `server/modules/ticket/service/ai/ticket_similar_result_cache_service.py`：

- **缓存对象**：`TicketReadService.get_similar_tickets` 的最终结果（symptom + case 两路），不是向量（向量已持久化在 `embedding_record` 表）。
- **缓存键**：`ticket:similar-result:{ticketId}:{limit}:{配置指纹}`；指纹取 sys_config `ticket.similarity.config` 原文 SHA-256 前 16 位，配置变更自然产生新键，旧键随 TTL 过期。
- **后端**：跟随 `CACHE_BACKEND` 配置。`redis`（当前 dev/prod 均为 redis）时使用**同步 Redis 客户端**独立建池（相似查询链路在 `run_in_threadpool` 同步线程内执行，不能复用 app.state 的 asyncio 客户端；与 asyncio 客户端共用同一 Redis 实例，key 前缀隔离）；`memory` 时降级为进程内 TTL 字典（上限 500 条）。
- **TTL**：5 分钟兜底，配合主动失效。
- **失效点**：① `TicketEmbeddingService.vectorize_ticket_for_scene` 向量刷新成功后（覆盖 manualCreate/manualUpdate/bitablePull/closeKnowledge 等全部自动场景）；② 相似案例状态变更接口 `POST /ticket/{ticket_id}/similarity-case/status` 提交成功后。
- **降级**：Redis 连接失败时自动降级为直查（返回 None 视为未命中），不影响接口可用性；读写异常只记日志不抛出。
- **不缓存 error**：`similarEmbeddingStatus=error` 的结果不写入缓存，下次查询仍走完整链路。

## 涉及文件

- 修改：`ticket_hybrid_similarity_service.py`（缩进修复）、`ticket_embedding_service.py`（失效点 1）、`ticket_crud_controller.py`（失效点 2）、`ticket_read_service.py`（缓存读写接入 + 指纹构建）
- 新增：`ticket_similar_result_cache_service.py`、`tests/test_ticket_similarity_cache.py`（6 用例）

## 验证结果

- `uv run ruff check`（本次 5 个改动文件）全部通过。
- `pytest tests/test_ticket_read_service.py tests/test_ticket_embedding_service.py tests/test_ticket_similarity_cache.py`：36 passed。
- 新增用例覆盖：三类信号都被查询、三类信号候选都进入候选集、memory 后端读写/失效/过期、缓存命中不触发完整链路、error 结果不缓存。
- Redis 真实连通性：本机到 dev（192.168.100.12:6633）/prod（10.56.130.136:7218）Redis 端口均超时不可达（网络隔离），已验证降级路径正常；**真实 Redis 读写需部署环境验证**。

## 注意事项

- 同步 Redis 池为懒加载单例，首次使用时建立；连接失败后每次调用会重试建池（3 秒超时），网络故障期间日志会有 warning 但接口不受影响。
- 工单更新后相似结果最长 5 分钟内可能仍为旧值（TTL 兜底窗口），主动失效已覆盖向量刷新与案例状态变更两个主路径。
- 配置指纹非字符串时（理论不应发生）回退 `default`，避免 Mock/异常对象产生不稳定指纹。
