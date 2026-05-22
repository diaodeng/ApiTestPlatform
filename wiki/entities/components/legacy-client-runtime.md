---
title: 旧版客户端运行时
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
  - client/src/common/appState.py
  - client/src/common/global_config_handler.py
  - client/src/do/config.py
  - client/src/do/pos_network.py
  - client/src/model/config.py
  - client/src/model/pos_network_model.py
  - client/src/server/config.py
  - client/src/server/agent_server.py
  - client/src/utils/common.py
  - client/src/utils/logger.py
---

# 旧版客户端运行时

旧版客户端运行时负责本地服务、配置、模型、工具函数和后台线程，是 Flet 壳层之下的支撑层。

```mermaid
graph TD
  A[common] --> B[共享状态/异常/配置]
  C[do] --> D[本地数据与网络处理]
  E[model] --> F[配置与网络模型]
  G[server] --> H[本地辅助服务]
  I[utils] --> J[文件/日志/定时器/代理]
```

## 参见

- [旧版客户端壳层](legacy-client-shell.md)
- [旧版 Flet 客户端](../services/legacy-flet-client.md)
- [旧版客户端功能模块](../services/legacy-client-features.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
