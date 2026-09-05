---
title: 工单相似度案例索引流程
type: flow
source_type: code
entry_points:
  - type: event
    trigger: 工单入库、更新、AI分析成功或RCA保存
  - type: http
    method: GET
    path: /ticket/{ticket_id}/similar-tickets
    trigger: 工单详情查询相似候选
  - type: http
    method: GET
    path: /ticket/{ticket_id}/summary
    trigger: 工单概览读取当前工单案例摘要（similarityCase 字段）
  - type: http
    method: POST
    path: /ticket/{ticket_id}/similarity-case/status
    trigger: 人工确认或驳回处理案例
created: 2026-08-30
updated: 2026-09-05
---

# 工单相似度案例索引流程

系统把表现相似和处理经验相似分开管理。表现相似向量使用标题、描述和稳定症状，处理经验案例使用证据、排查、根因、方案和验证结果。项目、模块、版本和环境作为结构化信号参与匹配，不直接承担自然语言语义。

```mermaid
sequenceDiagram
  participant T as 工单业务
  participant P as 相似画像服务
  participant E as EmbeddingRecord
  participant Q as 混合召回服务
  participant A as AI分析
  participant C as 案例表
  participant U as 操作人

  T->>P: 保存已知环境、版本和精确信号
  P->>E: 按现有场景开关生成 symptom 向量
  U->>Q: 打开详情查询相似工单
  Q->>Q: 精确/关键词候选 + MySQL 分批向量扫描 + 重排
  Q-->>U: 返回分数、命中原因、冲突和案例状态
  A->>Q: 读取候选进行逐条证据比较
  A->>C: AI成功后创建 draft 案例
  U->>C: 确认 verified 或驳回 rejected
  C->>E: 事务提交后异步生成对应案例向量
```

## 数据职责

- `ticket`：工单业务主数据和 RCA 事实回写字段。
- `ticket_similarity_profile`：环境和画像版本等一对一检索画像。
- `ticket_similarity_signal`：错误码、Trace ID、Request ID 等可建立普通索引的精确信号。
- `ticket_similarity_case`：案例状态、案例文本摘要、确认信息和索引状态。
- `embedding_record`：按 `embedding_scope` 保存实际向量；旧记录默认为 `symptom`。

## 规则

- 缺少项目、模块、版本或环境不会阻塞入库，也不会因为候选字段为空而误判冲突。
- 明确相同的错误码、Trace ID、项目、模块或环境会增加匹配依据；明确不同的信号会标记冲突并降权。
- `status=closed`、AI分析成功、`processed_at` 或 `issue_confirmed` 不能单独把案例标记为 `verified`。
- 案例确认不等于 Issue 归因，相似度不会自动更新 `ticket.issue_id`。
- 普通评论不触发单条 Embedding；只有评论内容被纳入有效画像、RCA 或案例后才更新索引。
- 生产默认使用外部 Embedding 和 MySQL 分批扫描，Qdrant 不属于本流程的生产前置依赖。

## 前端确认入口（2026-09-05 补齐）

- 工单列表详情弹窗"概览"页的"处理案例相似"卡片顶部展示当前工单案例摘要，提供确认案例（信息不完整时禁用）、回退草稿、驳回案例（需填驳回原因）三个操作，权限 `ticket:similarity:case`，与后端接口一致。
- 概览接口 `GET /ticket/{ticket_id}/summary` 响应新增 `similarityCase` 摘要字段（`TicketSummaryModel`），未形成案例时 `caseStatus=none`。
- 独立只读详情页仅展示案例状态，不提供写操作；状态变更成功后前端同时刷新概览与相似结果（后端已失效相似缓存）。
