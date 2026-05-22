---
title: 项目目的
type: purpose
source_type: mixed
created: 2026-05-20
updated: 2026-05-20
---

# 项目目的

项目定位为一套基于 FastAPI + Vue3 的接口测试与测试管理平台，覆盖接口管理、用例管理、测试套件、报告、定时任务、客户端转发与工单等能力。

```mermaid
mindmap
  root((QTestRunner 目标))
    测试管理
      用例管理
      测试套件
      报告管理
    平台治理
      用户与权限
      日志与监控
      定时任务
    执行能力
      客户端执行
      Web 测试
      桌面测试
```

## 参见

- [项目总览](overview.md)
- [架构总览](concepts/architecture-overview.md)
- [模块全景图](concepts/module-landscape.md)

## 被引用

- [后端应用服务](entities/services/backend-application.md)
- [HTTP API 入口流程](flows/http-api-entrypoint.md)
