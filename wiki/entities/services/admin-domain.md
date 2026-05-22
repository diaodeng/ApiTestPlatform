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
updated: 2026-05-20
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

## 参见

- [模块全景图](../../concepts/module-landscape.md)
- [系统管理数据模型](../data-models/admin-core-models.md)

## 被引用

- [项目总览](../../overview.md)
- [模块全景图](../../concepts/module-landscape.md)
