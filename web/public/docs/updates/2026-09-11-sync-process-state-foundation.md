# 2026-09-11 同步过程状态宽表阶段 2b（存储地基交付 + 服务层切换蓝图）

## 背景

接续 [AI 结果回帖阶段二](2026-09-11-ai-reply-phase2.md) 待办：发布状态（`publish_*`）与群推送执行状态（`group_push_*`）仍存于 `ticket.extra_data` JSON，整包读改写下 AI 终态回调与后处理批次并发互相覆盖（生产 INC00001934853R 17:32:05/07 实测），且群推送去重锁依赖锁 `ticket` 行。本批交付宽表**存储地基**（DDL + DO + DAO + 测试，纯增量零行为影响），服务层切换按下方蓝图实施。

## 本批交付

- `server/sql/20260911_ticket_sync_process_state.sql`：`ticket_sync_process_state` 建表（一工单一行，发布域 5 列 + 群推送执行域 8 列）。建表后部署无行为影响（无人读写），可与阶段一发版窗口一并执行。
- `server/modules/ticket/entity/do/ticket_sync_process_state_do.py`：DO 实体。
- `server/modules/ticket/dao/ticket_sync_process_state_dao.py`：DAO，关键契约——
  - **按域更新**：`update_publish_state`（发布域）/ `update_push_fields`（推送域，白名单拒绝跨域字段），严禁全量字段覆盖，防止宽表退化为新的整包读改写；
  - **行级锁**：`get_state(for_update=True)` / `ensure_state`（行不存在创建）；
  - **处理锁语义**：`acquire_push_processing_lock`（已发送过/占用未超时/超时抢占三态）+ `release_push_processing_lock`（幂等）+ `mark_push_sent_once`（标记同时清锁）；
  - `list_states_for_pull`：delivery 拉取链路批量查询。
- `server/tests/test_ticket_sync_process_state_dao.py`：13 用例覆盖按域更新白名单、锁抢占/占用/超时/幂等释放、默认态、批量映射。

## 设计决策（已定，实施时不再议）

1. **automation 步骤状态（`sync_state.automation.steps`）保留 JSON 不进宽表**：它是 build_meta 白名单透传的 dict、非擦除受害者，写入方分散在 10+ 文件，列化收益不覆盖改造成本。
2. `ai_task_status` 归发布域进宽表（由 `update_publish_state` 一并写）。
3. `sync_state` 交付协议域（`status/consumers/last_batch_id/last_consumer/last_pulled_at/revision/sync_scene` + automation）保留 JSON——那是外部同步 pending/ack 协议本体。

## 服务层切换蓝图（下一会话实施）

**group_push_service**（影响面已核实：状态方法 13 处调用全部在本文件内）：
- `set_publish_state`/`is_publish_ready`/`can_recover_publish_state`/`ensure_publish_ready_for_pull` → 改走 `update_publish_state`/`get_state`；
- `is/mark_group_push_sent_once`、`mark/clear/is_group_push_processing_locked` → 删除，改走 DAO 锁方法；
- `persist_group_push_meta_state` → 重构：锁状态行（acquire → mark/release），不再写 extra_data 状态键，锁目标从 `ticket` 行变为状态行；
- `resolve_ai_pending_state` 的 `ai_task_status` 读取、`finalize_sync_after_ai`/`finalize_publish_state_after_post_process`/`send_auto_group_message_once`/`send_group_message_for_ai_reply`/`send_ai_result_thread_reply`/`send_group_push_by_ticket_no_services` 调用点适配；
- automation 步骤回写（`_apply_ai_terminal_status_to_automation_step`）仍走 `persist_sync_meta`。

**其他调用方**（已核实数量）：`ticket_sync_delivery_service`（syncSummary 改读 `list_states_for_pull`、pending 前检查 2 处）、`ticket_sync_service`（ai_task_status 1 处）、`ticket_sync_notify_service`（3 处）、`ticket_sync_payload_service`（1 处）。

**收尾**：两处 `build_meta` 白名单删除 `publish_*`/`ai_task_status`/`group_push_*` 状态键（同阶段一 refs 拆除模式）；新增回填脚本 `migrate_sync_process_state.py`（从 sync_state 旧键回填宽表行，preview/apply 两段式）。

**必做回归测试**：R 单 17:32 场景——AI 终态回调与后处理批次并发收敛发布状态，宽表行锁下后写者必须在前写者提交后才更新（不得互相覆盖丢中间状态）。

**部署顺序**：本批 DDL 可随阶段一窗口执行 → 服务切换版本部署前执行回填脚本 → 部署（顺序不可颠倒，同阶段一）。

## 验证

- pytest：`test_ticket_sync_process_state_dao.py` 13 用例 + 回帖/补发/场景套件共 71 用例（含 12 subtests）全部通过。
- ruff：新文件全部通过；ORM 元数据注册确认（`Base.metadata.tables` 含新表）。
- 未执行：生产建表（维护窗口动作）、服务层切换（本批范围外）。
