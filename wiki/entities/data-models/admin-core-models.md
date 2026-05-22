---
title: 系统管理核心数据模型
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
  - server/module_admin/entity/do/user_do.py
  - server/module_admin/entity/do/role_do.py
  - server/module_admin/entity/do/menu_do.py
  - server/module_admin/entity/do/dept_do.py
  - server/module_admin/entity/do/post_do.py
  - server/module_admin/entity/do/dict_do.py
  - server/module_admin/entity/do/config_do.py
  - server/module_admin/entity/do/notice_do.py
  - server/module_admin/entity/do/log_do.py
  - server/module_admin/entity/do/job_do.py
  - server/module_admin/entity/do/api_key_do.py
---

# 系统管理核心数据模型

该数据模型簇覆盖用户、角色、菜单、部门、岗位、字典、配置、公告、日志、任务和 API Key。

```mermaid
erDiagram
  SysUser ||--o{ SysUserRole : has
  SysUser ||--o{ SysUserPost : has
  SysRole ||--o{ SysRoleMenu : has
  SysRole ||--o{ SysRoleDept : has
  SysDictType ||--o{ SysDictData : contains
  SysJob ||--o{ SysJobLog : produces
```

## 主要实体

- `SysUser`、`SysRole`、`SysMenu`、`SysDept`、`SysPost`
- `SysDictType`、`SysDictData`、`SysConfig`、`SysNotice`
- `SysLogininfor`、`SysOperLog`、`SysJob`、`SysJobLog`、`SysApiKey`

## 参见

- [系统管理域](../services/admin-domain.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [系统管理域](../services/admin-domain.md)
