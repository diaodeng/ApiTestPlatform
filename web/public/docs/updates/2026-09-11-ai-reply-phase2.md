# 2026-09-11 AI 结果回帖阶段二（oncePerTicket / 抢占式幂等 / 手动补发）

## 背景

接续 [群推送锚点拆表迁移（阶段一）](2026-09-11-group-push-anchor-table-migration.md)。本批为阶段二第一批（2a）交付三项独立能力；发布/推送编排状态宽表（`ticket_sync_process_state`）为阶段 2b 另行实施。

## 变更内容

### 1. `oncePerTicket` 幂等粒度配置（默认关闭，保持任务级现状）

- `aiResultFollowUp` 新增 `oncePerTicket`（默认 `false`）：false 任务级（同一分析任务只回一次，多次分析多次回帖，现状语义）；true 工单级（该工单回帖成功过一次后，后续分析不再回帖）。
- 判定走 `TicketAiDao.has_any_result_replied`（工单下任一任务 `result_replied_at` 非空即回帖过）；手动提交分析选择「本次回帖」（override=on）时跳过该限制。
- 前端：同步自动化页「AI 分析结果话题回帖」区块新增「每工单仅回帖一次」开关。

### 2. 回帖幂等升级为抢占式标记

- 原流程"先发送后标记"存在并发窗口（两个终态回调同时判定未回帖、重复发送）；现改为**发送前先占坑**（条件 UPDATE `result_replied_at` 并立即提交，并发下只有一个写者成功）→ 占坑失败即跳过 → 发送。
- 失败补偿：全部群发送失败时释放占坑（`release_result_replied` 置回 NULL），允许后续重试或手动补发；部分成功则保留标记并补写覆盖群审计列（`update_result_replied_chat_ids`）。

### 3. AI 结果回帖手动补发接口

- `POST /ticket/{ticket_id}/ai-analysis/tasks/{task_id}/reply-resend`（权限复用 `ticket:ai:analysis:run`）。
- 面向"分析已完成但结果未回帖"的任务（锚点丢失的历史工单、发送失败、当时配置未开启）；**不重新执行分析**，直接读取任务持久化结果渲染发送。
- 补发视为明确手动意图：强制 enabled+sendOn=always、override=on（跳过总开关/时机匹配/工单级幂等），但保留任务级幂等（已回帖任务拒绝）、无锚点策略与凭证判定；结果写入工单事件（`手动补发AI结果回帖`）。
- 存量补发路径：INC00001934853 等锚点丢失工单，先手动按工单号发群消息建立锚点（阶段一后锚点持久保留），再对成功任务调本接口补发，无需重跑分析。

## 变更文件

- `server/modules/ticket/service/sync/ticket_sync_config_service.py`（oncePerTicket 归一化）
- `server/modules/ticket/service/sync/ticket_sync_group_push_service.py`（oncePerTicket 判定 + 抢占式标记/失败释放）
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`（补发服务 `resend_result_reply_services`）
- `server/modules/ticket/controller/ticket_ai_controller.py`（补发路由）
- `server/modules/ticket/dao/ticket_ai_dao.py`（`has_any_result_replied` / `release_result_replied` / `update_result_replied_chat_ids`）
- `web/src/views/ticket/syncAutomation/index.vue`、`hooks/useSyncConfig.js`（oncePerTicket 开关）
- `server/tests/test_ticket_ai_result_follow_up.py`（+3 用例）、`server/tests/test_ticket_ai_reply_resend.py`（新增 7 用例）

## 验证

- pytest：回帖/补发/场景/任务状态/自动化复用/Agent 调度套件 77 用例（含 12 subtests）全部通过。
- ruff：改动文件通过（`ticket_sync_config_service.py` 11 个 E501 为存量告警，非本次引入）。
- 前端 `npm run build:prod` 通过。
- 未执行：生产端到端补发（需发版后按存量工单验证）。

## 待办（阶段 2b）

- `ticket_sync_process_state` 宽表：发布状态、群推送执行状态、自动化步骤列化，`persist_group_push_meta_state` 行锁从工单行迁到状态行，根治 AI 终态与后处理并发写 `extra_data` 的 last-writer-wins（R 单 17:32 竞争场景需写成并发回归测试）；涉及 delivery 的 syncSummary 出参保持不变。
- 回帖状态详情页可视化（已回帖时间/跳过原因展示）。
