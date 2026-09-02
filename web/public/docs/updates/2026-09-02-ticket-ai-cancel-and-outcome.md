---
title: AI分析任务取消、提交结果类型标识与并发锁标识
---

# AI分析任务取消、提交结果类型标识与并发锁标识

## 变更日期

2026-09-02

## 变更概述

工单 AI 分析第三阶段落地，共四项：

1. **协作式任务取消**：新增 `POST /ticket/{ticketId}/ai-analysis/tasks/{taskId}/cancel` 接口。取消时服务端先把任务置为"已取消"并写审计与工单事件，再向 Agent 发送取消通知；Agent 在 Worker 执行前、执行后两个检查点感知取消标记——执行前取消则放弃启动 Worker（零消耗），执行中取消则放弃回传结果（已消耗的 token 仍如实计入审计）。Worker 完成后回传的迟到结果不会覆盖取消态。
2. **提交结果类型标识（outcome）**：创建和重试接口的响应新增 `outcome` 字段，区分四种情况：`created`（新建任务）、`retried`（重试原任务）、`attached`（相同请求已在执行中，已关联原任务）、`reused`（命中历史成功结果，直接返回）。前端据此显示不同提示，不再一律显示"已提交"。
3. **执行中锁冲突携带任务标识**：Agent 返回 `AI_TASK_ALREADY_RUNNING` 时附带 `running_task_id` / `running_ticket_id`，服务端可据此定位正在执行的原任务（接管等待或引导取消），不再只能让用户盲等。
4. **任务历史新增"取消"按钮**：待执行/执行中状态的任务显示取消入口（需 `ticket:ai:analysis:run` 权限），二次确认后执行取消。

## 用户可见变化

- AI 分析提交/重试后，提示语区分"已提交 / 已重新提交 / 已关联执行中任务 / 已返回历史结果"，能明确知道这次操作实际发生了什么。
- 任务历史中，执行中的分析任务可以主动取消；取消后任务显示"用户取消"，已发生的模型消耗仍可在 AI 执行审计中看到。
- 相同请求重复提交时，页面明确提示"已为您关联原任务"，避免误以为发起了第二次分析。

## 涉及文件

- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：
  - `cancel_analysis_task_services` 取消服务（状态校验、置 canceled、释放活跃锁、写审计与事件、通知 Agent）；
  - `_notify_agent_task_canceled` fire-and-forget 取消通知（直发 WebSocket 分片，不等响应）；
  - `_process_task` 回传后重读任务状态：已取消则丢弃结果、仅补 token 进审计。
- `server/modules/ticket/controller/ticket_ai_controller.py`：新增 cancel 路由（权限同重试 `ticket:ai:analysis:run`）。
- `server/module_admin/entity/vo/common_vo.py`：`CrudResponseModel` 新增可选 `outcome` 字段。
- `client_new/server/agent_server.py`：`AI_TASK_CANCEL_FLAGS` 取消标记表；`handle_message_chunk` 识别 `cancel_task` 消息并注册标记（不进入业务转发）；`is_task_canceled` / `clear_task_cancel_flag` 查询与清理接口。
- `client_new/services/ticket_ai_analysis_service.py`：
  - Worker 执行前/执行后取消检查点（`_check_task_canceled`）；
  - 取消时返回结构化 `canceled` 状态（`AI_TASK_CANCELED`）并携带已消耗 token；
  - `AI_TASK_ALREADY_RUNNING` 返回携带 `running_task_id` / `running_ticket_id`。
- `web/src/api/ticket/ticket.js`：新增 `cancelTicketAiAnalysis`。
- `web/src/views/ticket/components/TicketDetailWithList.vue`：`showOutcomeMessage` 按 outcome 区分提示；任务历史"取消"按钮与确认弹窗；取消后刷新列表与详情。

## 行为边界

- 只允许取消 created/running 任务；终态任务调用取消接口幂等返回"任务已结束，无需取消"。
- 取消通知是尽力而为：Agent 离线或发送失败时取消仍在服务端生效，Worker 迟到结果会被"回传后重读状态"逻辑丢弃写回（不覆盖取消态）。
- Worker 执行中取消时，模型调用可能已完成或部分完成，这部分真实消耗会通过 Agent 返回的 `token_usage` 计入审计，不会丢失也不会伪造。
- 取消标记在任务终态后自动清理（Worker finally 与检查点命中时双保险），不会跨任务误伤。
- Agent 旧版本不识别 `cancel_task` 消息：会因未知 requestType 跳过，取消仍在服务端生效，行为退化为"服务端取消 + 迟到结果丢弃"，两端都升级后才完整支持执行中停止。
- 服务端、Agent 需同时部署：只升级服务端时 Agent 收不到取消标记（Worker 会继续执行到结束）；只升级 Agent 时无取消入口（不影响其他功能）。

## 注意事项

- 取消是协作式的：Worker 在检查点之间（单个模型调用进行中）无法被立即打断，取消后最多等待当前步骤结束。
- 取消已占用活跃锁的任务会立即释放活跃锁，同指纹新任务可立即提交；但若旧 Worker 因 Agent 旧版本未感知取消而继续执行，新任务会在 Agent 侧命中工作区锁（`AI_TASK_ALREADY_RUNNING`，响应中已携带原任务 ID 供定位）。
