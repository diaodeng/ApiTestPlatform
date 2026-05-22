---
title: 新版客户端壳层
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
  - client_new/main.py
  - client_new/ui/main_window.py
  - client_new/ui/theme_manager.py
  - client_new/ui/utils/single_instance.py
  - client_new/ui/utils/icon_util.py
---

# 新版客户端壳层

新版客户端壳层负责 PySide6 启动、单实例、主窗口、主题、图标和窗口生命周期管理。

```mermaid
graph TD
  A[main.py] --> B[异常与 Qt 消息处理]
  B --> C[单实例管理]
  C --> D[QApplication]
  D --> E[主题管理]
  D --> F[主窗口]
  F --> G[页面与对话框]
  F --> H[关闭清理]
```

## 参见

- [新版 PySide6 客户端](../services/new-pyside-client.md)
- [新版客户端运行时](new-client-runtime.md)
- [新版客户端服务模块](../services/new-client-services.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
