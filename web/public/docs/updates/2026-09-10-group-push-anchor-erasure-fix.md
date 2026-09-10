# 2026-09-10 群推送话题锚点被同步更新静默擦除导致 AI 结果回帖跳过修复

## 问题现象

用户反馈工单 INC00001934853 / INC00001934853R 的 AI 分析已在生产环境成功完成，但工单群里始终没有收到「AI 分析结果」的话题回帖。

## 排查结论

- `.env.prod` 与本问题无关：回帖功能的全部开关都在数据库 `sys_config('ticket.sync.automation')` 中，生产配置正确（`groupPush.enabled=true`、`sendMode=feishu_app`、`aiResultFollowUp.enabled=true`、`sendOn=success`）。
- 生产库直查发现两单 `group_push_sent_once=true`（群消息发送过）但 `sync_state.group_push_message_refs`（话题锚点）为 `null`、`ai_result_reply_task_ids`（回帖幂等记录）为空。
- 回帖链路 `finalize_sync_after_ai` → `send_ai_result_thread_reply` 依赖锚点定位话题；无锚点时按 `noAnchorStrategy=skip`（生产当前配置）只记日志跳过。

## 根因

`TicketSyncGroupPushService.build_meta` 与 `TicketSyncPayloadService.build_meta` 用白名单重建 `sync_state`，白名单未包含 `group_push_message_refs` 与 `ai_result_reply_task_ids`。任何走「build_meta → attach_meta → 写库」的链路（每次外部同步更新 / 多维表格拉取轮询都会走）都会把这两个字段静默清空。

时间线（原单）：09:46:43 创建后推送群消息（锚点写入）→ 09:50、09:55 两次外部同步更新（锚点被擦除）→ 11:11 AI 完成触发回帖时无锚点被 skip。R 单同理（AI 终态收敛与后处理批次并发写 meta 竞争，之后多次同步更新同样擦除）。

该缺陷自 2026-08-07 锚点功能引入即存在；影响所有「先推送群消息、后完成 AI 分析、中途有同步更新」的工单。`web/public/docs/changelog/2026-09-07-ai-result-thread-reply.md` 中"历史无锚点属 09-04~09-07 一次性数据缺口"的判断不成立。

## 变更内容

1. `server/modules/ticket/service/sync/ticket_sync_group_push_service.py`：`build_meta` 白名单补齐 `group_push_message_refs`、`ai_result_reply_task_ids`（缺失时补空列表）。
2. `server/modules/ticket/service/sync/ticket_sync_payload_service.py`：同上同步补齐。
3. `server/tests/test_ticket_sync_ai_finalize_scene.py`：新增 `TestBuildMetaKeepsGroupPushRefs` 回归测试 6 个（两处 build_meta 分别验证锚点/幂等保留、默认空列表、往返组合保留）。
4. `web/public/docs/ticket-sync-automation.md`：⑧ 回帖章节补充锚点持久化说明与「如何手动补发 AI 结果回帖」操作指引。

未做任何数据修复脚本：存量被擦除锚点的工单（含本次两单）无法自动恢复锚点，按文档指引手动补发。

## 验证

- pytest：`test_ticket_sync_ai_finalize_scene.py` + `test_ticket_ai_result_follow_up.py` 共 53 用例（含 12 subtests）全部通过；`test_ticket_sync_automation_reuse.py` 通过。
- `test_ticket_sync_mapping_boundary.py` 13 个失败经 git stash 基线对比确认为存量问题，与本次无关。
- ruff：3 个改动文件全部通过。
- 未执行：生产环境端到端补发验证（需发版后用新工单观察；或对两单执行文档中的手动补发流程）。

## 剩余风险

- 发版前，所有进行中的工单在"群推送之后、AI 完成之前"发生外部同步更新仍会丢锚点。
- 手动 AI 分析选择「本次回帖」时，若全局 `sendOn` 配置结构无效（非法值按 none 处理）仍会跳过，这是保留的既有语义。
