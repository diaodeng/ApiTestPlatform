---
title: 内容目录
type: index
source_type: code
created: 2026-05-20
updated: 2026-09-21
---

# 内容目录

## 总览

- [项目总览](overview.md)

## 概念

- [架构总览](concepts/architecture-overview.md)
- [双客户端架构](concepts/desktop-client-architecture.md)
- [模块全景图](concepts/module-landscape.md)
- [工单项目版本中心](concepts/ticket-version-center.md)

## 实体

- [后端应用服务](entities/services/backend-application.md)
- [后端基础设施层](entities/components/server-infrastructure.md)
- [系统管理域](entities/services/admin-domain.md)
- [HRM 测试管理域](entities/services/hrm-domain.md)
- [QTR 执行域](entities/services/qtr-domain.md)
- [任务调度域](entities/services/task-scheduler-domain.md)
- [工单域](entities/services/ticket-domain.md)
- [工单自定义实时统计服务](entities/services/ticket-custom-statistics.md)
- [系统管理核心数据模型](entities/data-models/admin-core-models.md)
- [HRM 核心数据模型](entities/data-models/hrm-core-models.md)
- [任务调度核心数据模型](entities/data-models/task-core-models.md)
- [工单核心数据模型](entities/data-models/ticket-core-models.md)
- [统一凭证数据模型](entities/data-models/credential-management.md)
- [配置任务资源与运行数据模型](entities/data-models/configuration-task-resource-models.md)
- [HRM 枚举集](entities/enums/hrm-enums.md)
- [工单枚举集](entities/enums/ticket-enums.md)
- [前端启动骨架](entities/components/frontend-bootstrap.md)
- [Web 控制台壳层](entities/components/web-shell.md)
- [Web 功能模块](entities/services/web-feature-domains.md)
- [旧版 Flet 客户端](entities/services/legacy-flet-client.md)
- [新版 PySide6 客户端](entities/services/new-pyside-client.md)
- [旧版客户端启动壳](entities/components/legacy-client-bootstrap.md)
- [新版客户端启动壳](entities/components/new-client-bootstrap.md)
- [旧版客户端壳层](entities/components/legacy-client-shell.md)
- [旧版客户端运行时](entities/components/legacy-client-runtime.md)
- [旧版客户端功能模块](entities/services/legacy-client-features.md)
- [新版客户端壳层](entities/components/new-client-shell.md)
- [新版客户端 pywebview 界面](entities/components/new-client-webview-ui.md)
- [新版客户端运行时](entities/components/new-client-runtime.md)
- [新版客户端服务模块](entities/services/new-client-services.md)
- [门店配置任务域设计](entities/services/configuration-task-domain.md)
- [门店配置运行取证与证据包实施方案](features/configuration-task-evidence-collection-plan.md)

## 流程

- [HTTP API 入口流程](flows/http-api-entrypoint.md)
- [工单流转路由流程](flows/ticket-workflow-routing.md)
- [工单问题实例关联流程](flows/ticket-issue-attribution-flow.md)
- [工单自动化链路流程](flows/ticket-automation-flow.md)
- [工单自定义统计通知流程](flows/ticket-custom-statistics-notification.md)
- [统一凭证刷新流程](flows/credential-refresh.md)
- [Web 录制流程](flows/ticket-recording-flow.md)
- [门店配置文件存储流程](flows/configuration-task-file-storage.md)
- [配置任务复用 Web 录制与执行](flows/configuration-task-web-reuse.md)
- [内存增长监控流程](flows/memory-growth-monitoring.md)
- [工单日志拉取记录独立查看流程](flows/ticket-log-record-isolated-view.md)

## 契约

- [工单自定义统计接口与配置契约](contracts/ticket-custom-statistics.md)
- [工单外部同步与内网拉取流程](flows/ticket-external-sync-flow.md)
- [统一凭证接口契约](contracts/credential-api.md)
- [配置任务文件协议](contracts/configuration-task-file-protocol.md)
