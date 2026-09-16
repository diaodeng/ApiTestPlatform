---
title: 自动拉日志同参数决策矩阵与拉取人列
date: 2026-09-09
type: feature
modules:
  - ticket-sync-automation
  - ticket-log-pull
related_docs:
  - ticket_log_pull.md
  - ticket-sync-automation.md
---

# 自动拉日志同参数决策矩阵与拉取人列（2026-09-09）

## 变更主题

1. **自动拉日志同参数决策矩阵**：修复外部工单重复同步导致同参数拉取记录反复创建的问题。此前自动链路只查"成功"记录去重，失败记录永远匹配不到，导致每次同步都新建一条注定失败的拉取记录，并重复发送失败通知。
2. **拉取记录新增"拉取人"**：日志拉取管理页与工单详情日志 Tab 新增「拉取人」列，自动拉取显示「自动」标签（悬停可看触发场景），人工拉取显示创建人用户名。
3. **终态写入防护**：修复"人工停止后，后台线程把状态覆盖回成功/失败"的竞态。

## 决策矩阵规则

自动化链路创建拉取前，按同参数（环境/商家/门店/POS/数据类型/日期/路径/时间范围）**最新一条记录**的状态决策：

| 最新记录状态 | 行为 |
|---|---|
| 不存在 / 已取消 | 创建新拉取 |
| 进行中 | 不创建，等待完成；场景要求 AI 而记录快照缺自动AI时只补缺失键合并配置 |
| 成功 | 复用；该记录无 AI 任务时触发自动 AI，已有成功/执行中任务或最近一次 AI 失败时跳过 |
| 失败 / 程序异常 | 静默跳过（不创建、不 AI、不通知），仅写工单事件与自动化日志留痕 |

失败静默的解锁方式：在日志拉取列表修正参数后**重新拉取**，新记录成为最新决策依据；重试成功后自动链路恢复复用。

## 数据库变更

需执行 `server/sql/20260909_ticket_log_pull_source.sql`（`ticket_log_pull_record` 新增 `pull_source`、`pull_source_scene` 两列）。存量数据无需回填：默认 manual，展示层按记录内自动化快照自动兜底识别。

## 行为变化说明

- 同参数失败的自动拉取不再每次同步重复创建与重复通知；如需重试请人工修正参数后重新拉取。
- 同参数进行中时自动链路不再并行创建第二条拉取；若该记录未勾选自动 AI 而场景要求 AI，会自动补充 AI 配置。
- 复用成功记录触发 AI 前会按记录级检查已有 AI 任务，避免重复分析。
- 人工停止记录后，后台线程不会再覆盖其状态；进行中记录停止后，同参数自动拉取允许重新创建。

## 涉及文件

后端：`ticket_log_pull_automation_decision_service.py`（新增）、`ticket_log_pull_service.py`、`ticket_log_pull_dao.py`、`ticket_ai_dao.py`、`ticket_sync_automation_service.py`、`ticket_log_pull_do.py`、`ticket_log_pull_vo.py`；前端：`constants.js`、`logPullRecord/index.vue`、`TicketDetailLogPullTab.vue`；测试：`test_ticket_log_pull_automation_decision.py`（新增 9 例）、`test_ticket_log_pull_terminal_guard.py`（新增 4 例）、`test_ticket_sync_automation_reuse.py`（适配）。

## 验证

- 决策矩阵 9 例 + 终态防护 4 例 + 既有复用/重试守卫/手工自动化测试共 32 例通过；
- ruff check 本次改动文件全部通过。
