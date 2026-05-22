---
title: 后端基础设施层
type: entity
entity_category: component
source_type: code
canonical: true
knowledge_state: stable
confidence: high
freshness: 2026-05-20
created: 2026-05-20
updated: 2026-05-20
related_files:
  - server/config/env.py
  - server/config/database.py
  - server/config/get_db.py
  - server/config/get_redis.py
  - server/config/celery_app.py
  - server/config/celery_scheduler.py
  - server/middlewares/handle.py
  - server/exceptions/handle.py
  - server/sub_applications/handle.py
  - server/common/permission/sync.py
---

# 后端基础设施层

后端基础设施层负责配置、数据库、Redis、Celery、中间件、异常处理和子应用挂载，是 `server/server.py` 的运行底座。

```mermaid
graph TD
  A[配置中心（config）] --> B[数据库]
  A --> C[Redis]
  A --> D[Celery]
  E[中间件层] --> F[请求/响应处理]
  G[异常层] --> F
  H[子应用挂载] --> I[静态资源/子服务]
  J[权限同步] --> K[菜单与权限注册]
```

## 职责

- 统一加载环境变量与运行配置。
- 维护数据库连接、ORM 类型和缓存连接。
- 注入中间件、异常处理和子应用。
- 支持权限菜单同步与启动期初始化。

## 参见

- [后端应用服务](../../entities/services/backend-application.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [模块全景图](../../concepts/module-landscape.md)
