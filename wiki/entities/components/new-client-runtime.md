---
title: 新版客户端运行时
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
  - client_new/common/appState.py
  - client_new/common/excptions.py
  - client_new/do/config.py
  - client_new/do/pos_network.py
  - client_new/emitter/mitm_flow_emitter.py
  - client_new/infra/process_manager.py
  - client_new/managers/pos_manager.py
  - client_new/model/config.py
  - client_new/model/pos_network_model.py
  - client_new/models/pos_state.py
  - client_new/server/config.py
  - client_new/server/agent_server.py
  - client_new/utils/common.py
  - client_new/utils/logger.py
  - client_new/workers/worker.py
  - client_new/workers/proxy_worker.py
---

# 新版客户端运行时

新版客户端运行时包含状态管理、进程管理、发射器、模型定义、本地服务、工具函数和后台 worker，是 PySide6 UI 之下的支撑层。

```mermaid
graph TD
  A[common] --> B[共享状态/异常]
  C[do] --> D[本地数据适配]
  E[models/model] --> F[UI 与业务模型]
  G[infra/managers] --> H[进程与实例管理]
  I[server] --> J[本地辅助服务]
  K[workers] --> L[后台任务]
```

## 参见

- [新版客户端壳层](new-client-shell.md)
- [新版 PySide6 客户端](../services/new-pyside-client.md)
- [新版客户端服务模块](../services/new-client-services.md)
- [模块全景图](../../concepts/module-landscape.md)

## 被引用

- [项目总览](../../overview.md)
- [双客户端架构](../../concepts/desktop-client-architecture.md)
