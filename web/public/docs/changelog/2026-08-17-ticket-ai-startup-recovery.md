---
title: 修复工单 AI 历史任务恢复导致服务启动失败
date: 2026-08-17
---

# 修复工单 AI 历史任务恢复导致服务启动失败

## 问题表现

生产服务启动时，如果数据库中存在 `created` 或 `running` 状态的工单 AI 分析任务，服务会先将这些任务清理为失败。

部分历史任务没有保存执行命令，恢复流程可能向数据库写入 `NULL`。由于 `ticket_ai_analysis_task.command_line` 是非空字段，数据库会报错：

```text
Column 'command_line' cannot be null
```

随后 FastAPI 启动失败，Supervisor 会自动重启 FastAPI 进程。

## 修复内容

- 状态更新时，如果没有执行命令，将 `command_line` 设置为空字符串。
- 如果任务已有执行命令，则继续保留原始命令内容。
- 新增单元测试，覆盖缺省命令和已提供命令两种情况。

## 影响范围

- 仅影响工单 AI 分析任务的状态更新和服务启动恢复流程。
- 不修改历史任务的其他字段。
- 不影响 Celery Broker、Redis 或数据库连接配置。

