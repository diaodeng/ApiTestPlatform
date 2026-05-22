---
title: 任务调度核心数据模型
type: entity
entity_category: data_model
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - server/module_task/celery_job_models.py
  - server/module_task/celery_job_vo.py
---

# 任务调度核心数据模型

任务调度核心数据模型围绕周期任务定义和执行日志展开。

```mermaid
erDiagram
  CeleryPeriodicTask ||--o{ CeleryTaskExecutionLog : produces
```

## 主要实体

- `CeleryPeriodicTask`
- `CeleryTaskExecutionLog`
- `JobModel` 与相关查询/编辑模型

## 参见

- [任务调度域](../services/task-scheduler-domain.md)

## 被引用

- [项目总览](../../overview.md)
- [任务调度域](../services/task-scheduler-domain.md)
