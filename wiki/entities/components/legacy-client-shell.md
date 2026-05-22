---
title: 旧版客户端壳层
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
  - client/src/main.py
  - client/src/navigationMenu.py
  - client/src/contents.py
  - client/src/view_contents/exitAlertDialog.py
---

# 旧版客户端壳层

旧版客户端壳层负责 Flet 应用启动、菜单导航、内容切换和退出确认，是历史桌面端的 UI 宿主。

```mermaid
graph TD
  A[main.py] --> B[Flet 页面]
  B --> C[导航菜单]
  C --> D[内容工厂]
  D --> E[页面缓存]
  B --> F[退出确认]
```

## 参见

- [旧版 Flet 客户端](../services/legacy-flet-client.md)
- [旧版客户端运行时](legacy-client-runtime.md)
- [旧版客户端功能模块](../services/legacy-client-features.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
