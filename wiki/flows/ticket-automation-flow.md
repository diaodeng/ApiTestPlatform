---
title: 工单自动化链路流程
type: flow
source_type: code
entry_points:
  - type: http
    method: POST
    path: /ticket
    trigger: 新增工单时可携带自动拉日志与自动AI配置
  - type: http
    method: POST
    path: /ticket/{ticket_id}/log-pulls
    trigger: 工单详情页或创建后自动提交日志拉取任务
  - type: http
    method: POST
    path: /ticket/{ticket_id}/ai-analysis
    trigger: 手工或日志拉取成功后触发AI分析任务
created: 2026-05-22
updated: 2026-05-28
---

# 工单自动化链路流程

该流程描述工单创建时可选的自动拉日志与日志后自动 AI 分析链路，以及手工日志拉取、手工 AI 分析共用的任务编排方式。

```mermaid
sequenceDiagram
  participant U as 工单操作人
  participant W as 工单前端
  participant C as ticket_controller
  participant S as TicketService/LogPullService/AIService
  participant A as Agent
  participant X as 外部日志平台

  U->>W: 新增工单，选择是否自动拉日志/自动AI
  W->>C: POST /ticket
  C->>S: 创建工单并在 extra_data 中记录自动化配置
  S->>S: 必要时同步创建日志拉取任务
  S->>X: 提交日志申请并下载/解析压缩包
  X-->>S: 返回压缩包或结果地址
  S->>S: 日志成功后检查 _automation 配置
  S->>C: 提交 AI 分析任务请求（含 agentCode）
  C->>A: 通过 WebSocket 发送 AI 分析任务
  A->>A: 本地执行 Codex Worker
  A-->>C: 回传 AI 分析结果
  C->>S: 回写工单 AI 分析结果 / RCA / 事件
  S->>S: 写入AI消息与ACR快照
  S->>S: 关闭工单时自动生成知识库案例
  S-->>W: 返回工单创建与自动化结果
```

## 入口信息

| 类型 | 方法 | 路径 | 触发条件 |
|---|---|---|---|
| http | POST | `/ticket` | 创建工单时可同时填写日志拉取与自动 AI 配置 |
| http | POST | `/ticket/{ticket_id}/log-pulls` | 工单详情页手工提交日志拉取，或工单创建后自动触发 |
| http | POST | `/ticket/{ticket_id}/ai-analysis` | 手工发起 AI 分析，或日志拉取成功后自动触发 |

## 详细步骤

| 步骤 | 说明 |
|---|---|
| 1 | 新增工单时，前端可勾选是否需要拉取日志，并在同一表单里填写日志拉取参数。 |
| 2 | 若勾选“日志后自动 AI”，前端同时要求选择 Agent，后端将 Agent 编码写入日志拉取记录的内部自动化配置。 |
| 3 | `TicketService.create_ticket` 在保存工单后可同步创建日志拉取任务，并把自动化配置写入工单 `extra_data.ticket_automation` 便于追溯；日志拉取服务会先查外部列表，已可下载时直接进入下载流程，否则再提交申请并轮询。 |
| 4 | `TicketLogPullService._process_record` 在日志拉取成功后读取记录中的 `_automation` 配置；该字段仅用于内部自动化联动，不参与外部平台轮询匹配。 |
| 5 | 若自动化配置开启 AI 且存在 Agent 编码，服务端构造 `TicketAiAnalysisRequestModel` 并触发分析任务。 |
| 6 | `TicketAiAnalysisService.create_analysis_task_services` 将请求里的 `agentCode` 写入任务上下文，后续由服务端编排到对应 agent。 |
| 7 | agent 端收到任务后执行本地 Codex Worker，结果再经 WebSocket 回传服务端入库；Worker 由后台线程执行，避免阻塞 WebSocket 事件循环；服务端在同一 Agent 有未完成请求时会跳过离线判定，并在完整响应分片到达后回写 Future；如果重试同一任务 ID，agent 会先检查工作区历史结果，存在可用结果则直接返回，任务仍在运行则提示稍后重试。AI 结果 schema 只强制核心分析字段，协同增强字段缺省时由服务端补默认值。 |
| 8 | 工单详情页中的时间线、日志拉取和 AI 分析改为按需加载，避免打开详情时一次性拉取大量数据。 |
| 9 | 协同追问会先写入 `ticket_message`，再复用 AI 分析任务入口读取消息流、快照和相似历史工单做增量分析；下发给 Agent 的日志正文会按首尾保留策略截断，避免超大上下文导致上游模型接口失败。 |
| 10 | AI 分析成功后写回 `ticket.ai_analysis`、RCA、AI 消息和 `ticket_snapshot`；工单关闭时自动提炼 `knowledge_article` 供后续相似工单检索。 |

## 错误处理

| 场景 | 处理方式 |
|---|---|
| 自动拉日志但缺少日志参数 | 创建工单前直接校验并返回失败，阻止生成不完整任务。 |
| 自动 AI 但未选择 Agent | 前端与后端都拒绝提交，避免任务落到默认 Agent。 |
| 日志拉取成功后自动 AI 提交失败 | 保留日志拉取成功结果，并在系统日志记录自动 AI 失败原因。 |
| Agent 不在线 | AI 分析任务失败，服务端返回明确的 agent 不在线提示。 |
| Codex/OpenAI 返回 `bad_response_status_code` | Agent 返回更明确的上游异常摘要；服务端通过日志截断和放宽增强字段必填约束降低重试失败概率。 |

## 参见

- [工单域](../entities/services/ticket-domain.md)
- [工单核心数据模型](../entities/data-models/ticket-core-models.md)
- [工单流转路由流程](ticket-workflow-routing.md)

## 被引用

- [内容目录](../index.md)
- [工单域](../entities/services/ticket-domain.md)
- [工单核心数据模型](../entities/data-models/ticket-core-models.md)
