---
title: 新增工单模块映射与修复脚本
date: 2026-08-14
---

# 新增工单模块映射与修复脚本

## 变更概述

- 新增一次性数据修复脚本 `server/scripts/sync_ticket_module_mapping.py`：按「工单同步自动化」配置中的 `moduleMappings` 将 `ticket.module_name`（工单现有模块名）与模块映射配置进行匹配，解析出正确模块后更新 `ticket.module_id`、`module_code`，**不改动 `module_name`**。
- 脚本不随应用运行，由人工按需手动执行（先预览确认后再更新）。

## 变更明细

### 新增脚本 `server/scripts/sync_ticket_module_mapping.py`

- 数据库连接配置从 `server/.env.prod` 读取；映射配置来源为 `sys_config` 表 `config_key='ticket.sync.automation'` 的 JSON 中 `moduleMappings` 字段。
- 匹配语义与运行时 `TicketSyncFieldMappingService` 保持一致：
  1. 映射条目配置了 `projectId` 时要求工单 `project_id` 与之相同，否则跳过；
  2. 关键字采用「包含」匹配（`module_name` 包含任意 `keywords` / `aliases` / `matchText` 即命中），按配置顺序取第一条。
- 模块解析只取 `hrm_module` 中 `status=2` 的正常模块：
  1. 工单有 `project_id`：优先按 `(project_id + module_code)` 查询，其次 `(project_id + module_id)`，再其次 `(project_id + module_name)`，避免跨项目同 `module_code` 串模块；
  2. 工单无 `project_id`：先按 `module_id`（全局唯一）查询，再按 `module_code` / `module_name`（必须全局唯一，多条则跳过并提示）。
- 更新值全部取自 `hrm_module` 实际行，保证 `module_id` 与 `module_code` 与模块表一致；解析结果与现状一致的工单自动跳过。
- 运行特性：整批更新走同一事务，异常整体回滚；运行前打印统计与明细并等待 Enter 确认（Ctrl+C 可取消）；支持 `python sync_ticket_module_mapping.py [limit]` 可选参数先小范围验证。

## 影响面

- 仅影响手动执行过该脚本的 `ticket` 行：更新 `module_id` / `module_code` 与 `update_time`，不修改 `module_name` 及其他字段。
- 首次执行建议先带 `limit` 参数小范围验证，确认预览内容符合预期后再全量执行。