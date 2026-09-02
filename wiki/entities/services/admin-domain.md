---
title: 系统管理域
type: entity
entity_category: service
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-09-02
related_files:
  - server/module_admin/controller/user_controller.py
  - server/module_admin/controller/role_controller.py
  - server/module_admin/controller/menu_controller.py
  - server/module_admin/service/user_service.py
  - server/module_admin/service/role_service.py
  - server/module_admin/service/menu_service.py
  - server/module_admin/dao/user_dao.py
  - server/module_admin/dao/role_dao.py
  - server/module_admin/dao/menu_dao.py
  - server/module_admin/entity/do/user_do.py
  - server/module_admin/entity/do/role_do.py
  - server/module_admin/entity/vo/user_vo.py
  - server/module_admin/perms.py
---

# 系统管理域

系统管理域负责用户、角色、菜单、部门、岗位、字典、参数、公告、日志、在线用户、缓存和 API Key 管理。

```mermaid
graph TD
  A[系统管理控制器] --> B[服务层]
  B --> C[DAO 层]
  C --> D[(系统管理数据表)]
  B --> E[权限注册]
  B --> F[导入导出与日志]
```

## 主要子模块

- 用户管理、角色管理、菜单管理、部门管理、岗位管理。
- 字典管理、参数管理、通知公告、日志管理。
- 在线用户、定时任务、服务监控、缓存监控、API Key。
- AI Provider、AI 提示词、AI 配置中心、AI 执行审计（`server/module_admin/controller/ai_task_execution_controller.py`，列表权限 `system:aitaskexecution:list`、详情权限 `system:aitaskexecution:query`；权限定义在 `server/module_admin/perms.py`，启动时 `sync_registered_menus` 自动落库，新按钮需在角色管理中授权后可见）。
- AI Provider 可观测上报（2026-09-02）：Provider 支持配置 OTLP 上报端点与鉴权（`observability_*` 字段，密钥 Fernet 加密）；工单 AI 分析在 `server/modules/ticket/service/ai/ticket_ai_observability_service.py` 中做任务级 LLM span 上报（`input.value`/`output.value`/`gen_ai.usage.*`，session=`ticket-ai-task-{taskId}`，旁路 best-effort），并按 `observability_cli_enabled` 向 client_new 下发 OTEL 环境注入本机 Codex（config.toml `[otel]` 托管段）与 Claude Code（环境变量 + `TRACEPARENT`）。

## 参见

- [模块全景图](../../concepts/module-landscape.md)
- [系统管理数据模型](../data-models/admin-core-models.md)

## 被引用

- [项目总览](../../overview.md)
- [模块全景图](../../concepts/module-landscape.md)
