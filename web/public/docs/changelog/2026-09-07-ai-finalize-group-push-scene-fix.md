# 2026-09-07 - 修复 AI 分析完成后自动群推送被错误场景拦截

## 问题现象

多维表格拉取（bitable_pull）场景的工单全链路自动执行成功（字段识别、AI 分类、自动拉日志、AI 分析均正常），但 AI 分析完成后没有向工单群发送任何消息；按工单号搜索服务端日志也找不到任何群推送相关记录。

典型案例：INC00001929286（2026-09-07 10:05 多维表格拉取入库，10:22 AI 分析成功，群推送静默丢失）。

## 根因

AI 分析任务到达终态后，服务端回写发布状态并补发自动群推送的链路（`finalize_sync_after_ai`）硬编码使用 `external_sync` 场景，而工单实际入库场景是 `bitable_pull`。群推送配置中 `sendAfterExternalSync=false`、`sendAfterBitablePull=true`，导致推送被外部推送场景开关拦截。拦截日志不包含工单号，按工单号搜索日志无法发现，形成排查盲区。

次要问题：

- 同步元数据没有持久化入库场景，异步回调（AI 终态）无法得知工单的真实触发场景。
- 群推送的多个跳过日志（enabled=false、sendAfterExternalSync=false 等）不打印工单号。
- 自动化步骤 `ai_analysis` 提交后一直停留在 `queued`，AI 终态从不回写，工单详情中显示状态失真。

## 变更内容

### 服务端

1. **同步元数据持久化入库场景**：`TicketSyncPayloadService.build_upsert_payload` 把 `sync_scene`（external_sync/remote_pull/bitable_pull/manual_create）写入 `extra_data.external_sync.sync_state.sync_scene`；两处 `build_meta`（payload 服务与群推送服务）白名单透传该字段。
2. **AI 终态回调按真实场景推送**：`TicketSyncGroupPushService.finalize_sync_after_ai` 不再依赖硬编码场景，改为从工单元数据解析：优先读 `sync_state.sync_scene`，历史工单没有该字段时按来源系统推断（`feishu_bitable_pull` → bitable_pull、`manual_create` → manual_create、其余保持 external_sync）。显式传入 `sync_scene` 参数仍优先（向后兼容）。
3. **排查盲区修复**：`TicketSyncNotifyService.send_group_message_for_ticket` 的场景开关拦截日志（enabled=false / sendAfterExternalSync=false / sendAfterRemotePull=false）全部补打工单号；AI 终态回调新增 `AI任务完成后群推送场景解析` 日志（含工单号与解析结果）。
4. **AI 终态回写自动化步骤**：AI 任务到达终态（成功/失败/取消）时同步更新 `sync_state.automation.steps.ai_analysis.status`（queued/running → success/failed/canceled），自动化整体状态随之收敛（全部步骤完成 → completed，AI 失败 → failed，其他步骤执行中 → running）。

### 测试

新增 `server/tests/test_ticket_sync_ai_finalize_scene.py`（17 个用例）：场景解析（持久化优先、非法值回退、来源系统推断、默认值）、两处 build_meta 透传、`finalize_sync_after_ai` 真实场景推送（持久化场景、历史推断、显式覆盖）、AI 终态回写自动化步骤（成功/失败/取消/其他步骤运行中/无步骤/非终态）。

### 用户文档

`web/public/docs/ticket-sync-automation.md`：发布状态章节补充 AI 终态场景解析与步骤回写说明；常见问题新增 Q6「AI 分析完成后没有发群消息怎么排查」。

## 影响与兼容性

- 新入库工单：场景随入库持久化，AI 终态回调按真实场景判断群推送开关。
- 历史存量工单（无 `sync_scene` 字段）：按来源系统推断，多维表格拉取来源（`feishu_bitable_pull`）可正确恢复场景；远端拉取来源系统可配置、无法与外部推送稳定区分，默认按外部推送处理（与修复前行为一致）。
- 已被 `group_push_sent_once` 去重的工单不受影响；本次修复前被误拦截的存量工单可用「操作」页签的手动群推送（`POST /ticket/sync/notify/group/send-by-ticket`）补发。
- 配置结构无变化，无需任何配置迁移。
