---
title: AI Provider 可观测上报（OTLP）
---

# AI Provider 可观测上报（OTLP）

## 变更日期

2026-09-02

## 变更概述

为 AI Provider 新增可观测上报能力（OpenTelemetry OTLP/HTTP），工单 AI 分析任务会把任务级 LLM 调用上报到可观测平台（如水滴引擎 `https://agents.dmall.com/observe`），实现"平台上看得到每次 AI 分析的输入、输出、Token 与耗时"。

整体链路分两层：

1. **任务级上报（Agent 侧）**：分析任务执行结束时，执行 Agent 将本次调用的最终提示词（INPUT）、分析结果 JSON（OUTPUT）、Token 用量、模型名、耗时、成功/失败状态按 OTLP 协议直连可观测平台上报；失败任务同样上报并带错误码。上报为旁路 best-effort，平台不可达时只记日志，不影响分析任务。（2026-09-02 修正：原设计为服务端上报，实测测试环境服务端与生产可观测平台网络隔离导致超时，已迁移至 Agent 侧——服务端只下发配置，不再出站上报。）
2. **CLI 原生遥测（可选，Agent 侧）**：Provider 可选开启"CLI 原生遥测"，Agent 会把 OTLP 配置注入本机 Codex（任务级 `config.toml` 的 `[otel]` 段）和 Claude Code（环境变量），CLI 自身的执行细节（工具调用、模型请求、事件日志）也会上报。Claude Code 通过 W3C Trace 上下文（`TRACEPARENT`）挂接到任务级 trace，Codex 通过相同 `session.id` 关联。

配套改动：

- `sys_ai_provider` 表新增可观测字段（迁移脚本 `server/sql/20260902_ai_provider_observability.sql`）。
- Provider 管理页新增"可观测上报"配置块（按开关联动显示，隐藏不清空；密钥加密存储、脱敏显示、留空保持不变）。
- 上报会话标识统一为 `ticket-ai-task-{任务ID}`，可观测平台 Sessions 页可按工单任务聚合，与 CLI 遥测互相关联。

## 用户可见变化

- AI Provider 新增/编辑弹窗多出"可观测上报"配置块：OTLP 端点、鉴权类型（Bearer/Basic）、鉴权密钥、Service 名称、CLI 原生遥测开关。
- 开启后，可观测平台 Traces 页可见 `service.name = ticket-ai-analysis`（或自定义名称）的任务级调用记录，INPUT/OUTPUT 列为完整提示词与分析结果。
- 开启"CLI 原生遥测"后，平台上还能看到本机 Codex / Claude Code 的细粒度执行 span。
- 不开启时行为与原来完全一致；上报配置不影响任务执行。

## 涉及文件

- `server/sql/20260902_ai_provider_observability.sql`：Provider 可观测字段迁移。
- `server/module_admin/entity/do/ai_provider_do.py`、`entity/vo/ai_provider_vo.py`、`service/ai_provider_service.py`：字段、校验与加密存储。
- `server/modules/ticket/service/ai/ticket_ai_observability_service.py`：新增，OTLP 任务级 span 上报子服务。
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：任务执行挂接上报；Provider 下发环境变量追加 CLI 遥测注入。
- `client_new/services/ticket_ai_codex_config_service.py`：新增任务级 config.toml `[otel]` 托管段写入（带标记整体刷新，写入后 TOML 校验）。
- `client_new/services/ticket_ai_analysis_service.py`：Claude 环境变量/`.env` 注入 OTEL 配置与 `TRACEPARENT`；Codex 启用开关对接。
- `web/src/views/system/aiprovider/index.vue`：Provider 表单可观测配置块。
- `web/public/docs/ai_provider_management.md`：用户说明新增"可观测上报（OTLP）"章节。