---
title: 旧版 Flet 客户端
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
  - client/src/main.py
  - client/src/navigationMenu.py
  - client/src/contents.py
  - client/src/view_contents/content_home.py
  - client/src/view_contents/content_agent.py
  - client/src/view_contents/content_pos_handler.py
  - client/src/view_contents/content_mitmproxy.py
  - client/src/server/agent_server.py
  - client/src/server/pos_config_server.py
---

# 旧版 Flet 客户端

旧版客户端是基于 Flet 的桌面应用，采用导航菜单 + 内容工厂的方式组织功能页，功能聚焦设置、商品、Agent、POS、mitmproxy、FTP、日志和关于页面。

```mermaid
graph TD
  A[入口（client/src/main.py）] --> B[Flet 页面初始化]
  B --> C[导航菜单（navigationMenu.py）]
  C --> D[内容工厂（contents.py）]
  D --> E[功能页集合]
  E --> F[本地工具服务]
  E --> G[日志与状态缓存]
```

## 职责

- 初始化 Flet 页面、窗口关闭拦截和底部状态栏。
- 根据导航栏选择懒加载功能页。
- 组织旧版客户端的本地服务、工具和日志视图。
- 提供商品、POS、Agent、mitmproxy、FTP 等功能入口。

## 主要模块

| 模块 | 作用 |
|---|---|
| `main.py` | 应用入口与页面布局。 |
| `navigationMenu.py` | 导航栏与内容切换。 |
| `contents.py` | 功能页工厂与缓存。 |
| `view_contents` | 各功能页 UI。 |
| `server` | 本地服务与辅助进程。 |
| `utils` | 日志、线程、文件与网络辅助。 |

## 参见

- [双客户端架构](../../concepts/desktop-client-architecture.md)
- [旧版客户端启动壳](../components/legacy-client-bootstrap.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
