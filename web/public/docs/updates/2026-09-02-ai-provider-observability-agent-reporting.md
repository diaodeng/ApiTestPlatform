---
title: 可观测上报迁移至 Agent 侧（服务端网络隔离修正）
---

# 可观测上报迁移至 Agent 侧（服务端网络隔离修正）

## 变更日期

2026-09-02

## 变更概述

实测发现：测试环境服务端与生产可观测平台（`agents.dmall.com`）网络隔离，服务端出站上报全部超时（任务正常成功但平台缺失任务级 span）。原"服务端上报任务级 span"的设计在该环境不可行，本次将上报链路迁移到 Agent 侧：

- **服务端**只负责解析 Provider 可观测配置并经 `providerEnv` 下发（OTLP 端点、鉴权头、service name、session id、trace id/span id）；不再出站上报，与平台网络隔离也不影响。
- **Agent（client_new）**在分析任务终态（成功/缓存命中/Worker 失败/结果无效/超时/异常六个出口）直连可观测平台上报任务级 span，数据比服务端更完整：INPUT 是最终渲染后的提示词（不再是模板占位符），OUTPUT 是分析结果，token/耗时/错误一并上报。
- 环境注入分层：可观测主开关开启即下发基础 OTLP 配置（供 Agent 任务span上报）；"CLI 原生遥测"开关额外下发 CLI 专属变量与 `TRACEPARENT`。CLI 开启时，任务 span 与 CLI span 共用同一 trace，Agent 任务 span 是父节点。
- 上报仍为旁路 best-effort：任何失败只记日志，绝不影响分析任务。

## 用户可见变化

- 可观测平台 Traces 页在服务端与平台网络隔离的环境下也能看到任务级记录（`ticket_ai_analysis`），INPUT 列为最终渲染的完整提示词。
- 服务端部署环境不再要求能访问可观测平台；要求变为"执行 Agent 的机器能访问 OTLP 端点"。
- 不开启"CLI 原生遥测"时平台也有任务级数据（此前该场景服务端超时导致一条都没有）。

## 涉及文件

- `client_new/services/ticket_ai_observability_service.py`：新增，Agent 侧任务级 span 上报子服务。
- `client_new/services/ticket_ai_analysis_service.py`：六个终态出口挂接上报。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：OTEL 环境注入分层（主开关=基础配置，CLI 开关=CLI 专属+TRACEPARENT）；移除服务端上报钩子。
- `server/modules/ticket/service/ai/ticket_ai_observability_service.py`：精简为仅配置解析（移除已迁移的上报方法）。
- `web/public/docs/ai_provider_management.md`：网络要求与上报架构说明修正。