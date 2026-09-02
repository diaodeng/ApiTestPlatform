---
title: AI分析并发防重、重试独立审计与Agent锁心跳续租
---

# AI分析并发防重、重试独立审计与Agent锁心跳续租

## 变更日期

2026-09-02

## 变更概述

工单 AI 分析第二阶段加固，共四项：

1. **并发提交防重（数据库级）**：两个请求几乎同时提交相同参数时，此前会在成功写回阶段才发现重复（败者任务仍会真实调用 Agent，白耗一次 token）。现在任务表新增"活跃锁"字段并建唯一索引：任务进入待执行/执行中时写入请求指纹，终态自动清空。并发创建同指纹任务时数据库直接拒绝第二个，前端会收到"已在执行中，直接返回原任务"，不会产生重复调用。
2. **重试独立审计**：此前重试会覆盖原审计记录，历次尝试的失败原因和 token 无法追溯。现在每次重试都会新建一条独立审计记录（标注尝试序号和上一次审计 ID），原审计记录保持终态不变。第一次失败消耗的 token 和第二次重试消耗的 token 各自可见、互不覆盖。
3. **复用结果留痕**：重复提交命中历史成功结果时，此前完全不留痕。现在会写入一条"复用历史结果"事件审计（不发起模型调用、不产生 token、不计入消耗统计），AI 执行审计页面显示"复用历史结果"状态。
4. **Agent 工作区锁心跳续租**：长任务此前靠"启动时间 + 超时×2"判定锁过期，超时后锁假死，新请求可抢占工作区、旧 Worker 若存活会并发写同一结果文件。现在 Worker 执行期间每 15 秒刷新锁心跳，心跳停止超过 60 秒才允许接管——Worker 活着锁就有效，Worker 崩溃后短窗口即可安全接管。旧版本锁文件仍按原时间窗判定，平滑兼容。

同时修复：任务执行入口增加状态白名单（只允许待执行/执行中进入执行），防止并发失败者（已取消）任务被误排队后再次执行、重复消耗模型调用。

## 用户可见变化

- 并发/重复提交相同分析参数不再可能触发两次真实模型调用，token 不会因此重复消耗。
- AI 执行审计页面中，重试会产生新记录而不是覆盖旧记录；可以完整看到每次尝试的时间、状态、错误和 token。状态列表新增"已取消（重复请求）"和"复用历史结果"。
- 复用历史成功结果的操作在审计中留痕，但不增加 token 统计。
- 长时间运行的 AI 分析不再有"锁过期后双 Worker 并发写结果"的风险。

## 涉及文件

- `server/modules/ticket/entity/do/ticket_do.py`：`ticket_ai_analysis_task` 新增 `active_lock` 字段与唯一索引。
- `server/config/get_db.py`：新增 `_ensure_ticket_ai_analysis_active_lock` 启动迁移（补列、清理存量值、建唯一索引）。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：
  - `_mark_task_status` 维护活跃锁（终态释放、活跃态按指纹占锁）；
  - 任务创建时直接占锁，并发冲突翻译为"复用原任务"幂等返回；
  - `_process_task` 执行入口状态白名单；
  - `retry_analysis_task_services` 重试新建独立审计记录（`attempt_of_task_id` / `attempt_no` / `prior_audit_execution_id`）；
  - `_record_reuse_event` 记录复用事件审计（`status=reused`、`usage_state=not_called`）。
- `client_new/services/ticket_ai_analysis_service.py`：新增 `_refresh_task_lock_heartbeat`、`_run_lock_heartbeat`（15 秒间隔）；`_is_stale_lock` 心跳优先判活、旧锁回退时间窗；Worker 执行段启动/取消心跳任务。
- `web/src/views/system/aitaskexecution/index.vue`：状态枚举与标签色补 `canceled`、`reused`。

## 行为边界

- 活跃锁只对"本变更之后创建的任务"生效；迁移会把存量任务的锁字段统一清空，不影响历史数据。
- "强制刷新"生成的请求指纹包含任务 ID，天然不会命中活跃锁，强制刷新行为不变。
- 重试审计记录沿用任务创建时的 Provider/模型配置；重试前的原审计记录（含其 token）保持不可变。
- 复用事件审计属于轻量事件，Token 统计聚合时只累计真实调用（`success/failed`），`reused` 状态不计入。
- 锁心跳为纯本地文件写，不产生网络流量；心跳间隔 15 秒、判活窗口 60 秒（间隔×4，下限 60 秒）。

## 注意事项

- 启动迁移会自动执行（补列 + 建唯一索引），首次启动时间略长属正常。
- AI 执行审计页面看"重试链"时，按 `requestPayload.attemptOfTaskId` 过滤同一任务的全部尝试，按 `attemptNo` 排序即为调用顺序。
- 服务重启恢复链路（第一阶段）与本次改动无冲突：恢复重新排队的任务在执行入口白名单内（状态为 created/running），可正常进入恢复写回。
