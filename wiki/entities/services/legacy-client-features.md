---
title: 旧版客户端功能模块
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
  - client/src/view_contents/content_settings.py
  - client/src/view_contents/content_goods.py
  - client/src/view_contents/content_agent.py
  - client/src/view_contents/content_pos_handler.py
  - client/src/view_contents/content_mitmproxy.py
  - client/src/view_contents/content_ftp.py
  - client/src/view_contents/content_log_view.py
  - client/src/view_contents/content_about.py
  - client/src/view_contents/content_shortcut.py
  - client/src/view_contents/content_fileSearch_back.py
---

# 旧版客户端功能模块

旧版客户端功能模块提供设置、商品、Agent、POS、mitmproxy、FTP、日志和关于页，是 Flet 时代的功能集合。

```mermaid
graph TD
  A[设置] --> B[工具配置]
  C[商品] --> D[商品/快捷方式]
  E[Agent] --> F[远程代理]
  G[POS] --> H[POS 控制]
  I[mitmproxy] --> J[流量抓包]
  K[FTP] --> L[文件服务]
  M[日志] --> N[运行记录]
```

## 参见

- [旧版客户端壳层](../components/legacy-client-shell.md)
- [旧版客户端运行时](../components/legacy-client-runtime.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
