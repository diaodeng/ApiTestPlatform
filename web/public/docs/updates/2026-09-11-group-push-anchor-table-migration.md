# 2026-09-11 群推送锚点与回帖幂等拆表迁移（阶段一）

## 背景

接续 [2026-09-10 群推送锚点擦除修复](2026-09-10-group-push-anchor-erasure-fix.md)：话题锚点（`group_push_message_refs`）与回帖幂等记录（`ai_result_reply_task_ids`）存于 `ticket.extra_data` JSON，被外部同步更新等链路的 `build_meta` 白名单重建静默擦除，导致 AI 分析结果不回帖工单群（生产 INC00001934853 / INC00001934853R）。白名单补齐只是止血；本次按既定方案拆表，从存储结构上根治——锚点与幂等不再参与 `extra_data` 整包读改写。

## 变更内容

### 1. 新表 `ticket_group_push_anchor`（锚点，一工单多行）

一条工单信息群消息一行（发几个群记几条），`message_id` 唯一约束天然去重，单工单保留最近 20 条（对齐拆表前截断语义）。DDL 见 `server/sql/20260911_ticket_group_push_anchor.sql`。

### 2. 任务表加幂等列 `ticket_ai_analysis_task.result_replied_at` / `result_replied_chat_ids`

回帖幂等回归天然主体（一行一任务）：`result_replied_at IS NULL` 即未回帖，替代原 JSON 任务 ID 列表 + 手工去重 + 50 条截断；标记用条件 UPDATE（`WHERE result_replied_at IS NULL`）保证并发下只有一个写者生效。

### 3. 服务层读写切换

- 群推送锚点写入（自动推送 `persist_group_push_meta_state` + 手动推送 `send_group_push_by_ticket_no_services`）改写锚点表，与状态更新同事务。
- 三处锚点消费方改查表：AI 结果回帖（`_collect_ai_result_reply_targets`）、飞书评论入站匹配（`_match_ticket_by_message_context`）、本地评论出站回复（`_resolve_feishu_reply_anchor`）。
- 入站匹配从「全表扫描工单逐单解析 JSON」改为按 message/root/thread 值索引查询锚点表——O(全表) → O(索引)，为拆表的附带性能收益。
- 回帖幂等检查/标记（`is/mark_ai_result_replied`）删除，改走 `TicketAiDao.is_result_replied / mark_result_replied`，保持"先发送后标记"现状语义（抢占式升级留给阶段二配合补发接口）。
- 两处 `build_meta` 白名单移除已拆字段，表为唯一事实源，防止双源。

### 4. 回填脚本 `server/scripts/migrate_group_push_anchor.py`

从存量工单 `extra_data` JSON 回填锚点表与幂等列；preview/apply 两段式、幂等可重跑、解析失败输出清单不静默跳过。生产 preview 实测：扫描 23 单，4 单有锚点存量、0 单有幂等记录（符合缺陷预期——幂等记录已被擦光）。

## 部署顺序（重要）

1. 维护窗口执行 `server/sql/20260911_ticket_group_push_anchor.sql`（建表 + 任务表加列）；
2. 执行 `cd server && uv run python scripts/migrate_group_push_anchor.py preview` 确认统计，再 `apply` 回填；
3. 部署新版服务端。

顺序不可颠倒：新代码读写全部走新表，若未回填先部署，存量锚点会失效（JSON 旧键停止读写）。

## 变更文件

- `server/sql/20260911_ticket_group_push_anchor.sql`（新增 DDL）
- `server/scripts/migrate_group_push_anchor.py`（新增回填脚本）
- `server/modules/ticket/entity/do/ticket_group_push_anchor_do.py`（新增 DO）
- `server/modules/ticket/entity/do/ticket_do.py`（任务表加幂等两列）
- `server/modules/ticket/dao/ticket_group_push_anchor_dao.py`（新增 DAO）
- `server/modules/ticket/dao/ticket_ai_dao.py`（加 is/mark_result_replied）
- `server/modules/ticket/service/sync/ticket_sync_group_push_service.py`（写入/收集/幂等切换 + 白名单移除）
- `server/modules/ticket/service/sync/ticket_sync_payload_service.py`（白名单移除）
- `server/modules/ticket/service/collaboration/ticket_message_sync_service.py`（入站匹配索引化 + 出站回复改查表）
- `server/tests/test_ticket_ai_result_follow_up.py`、`tests/test_ticket_sync_ai_finalize_scene.py`（测试改造：DAO 打桩 + 白名单排除断言）

## 验证

- pytest：回帖/场景/自动化复用/评论同步相关套件 52+ 用例（含 12 subtests）全部通过。
- ruff：全部改动文件通过。
- 回填脚本对生产库 preview 连通验证通过（只读不动库）。
- `test_ticket_processing_metrics.py` 3 个失败经基线对比确认为存量问题，与本次无关。
- 未执行：apply 回填与新代码生产端到端（按上述部署顺序在维护窗口进行）。

## 后续（阶段二，另行实施）

- 发布/推送编排状态收敛为 `ticket_sync_process_state` 宽表（根治行锁耦合与并发 last-writer-wins）；
- `aiResultFollowUp.oncePerTicket` 配置（默认 false 保持任务级幂等）；
- 回帖状态详情页可视化与已完成任务手动补发接口；
- 幂等升级为抢占式标记（先占坑后发送 + 失败补偿）。
