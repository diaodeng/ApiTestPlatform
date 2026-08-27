---
title: 工单 AI Agent 响应 JSON 校验修复
---

## 背景

工单 AI 分析通过本机 Agent 网关等待 Worker 执行完成后，服务端会把网关返回的 `HandleResponse` JSON 再次反序列化。

## 问题现象

- 页面任务历史中直接显示：`Cannot check isinstance when validating from json, use a JsonOrPython validator instead.`
- 实际 Agent 日志里已经包含更具体的 Worker 失败原因，例如 PowerShell heredoc 语法不兼容、Provider 鉴权失败等，但页面上看不到。

## 根因

`HandleResponse.response` 联合类型里包含 `AgentResponse`、`AgentResponseWebSocket` 等需要基于 Python 对象做 `isinstance` 判断的类型。服务端原先使用 `model_validate_json` 直接校验原始 JSON 字符串，Pydantic 在 JSON 校验阶段无法完成这类判断，于是先抛出了框架级异常，覆盖了 Agent 的真实失败信息。

## 修复内容

1. 为 `HandleResponse` 增加统一的传输负载反序列化入口，先把 HTTP/Redis 中的 JSON 字符串解析为 Python 字典，再执行 `model_validate`。
2. 工单 AI 网关调用与 Agent 分发缓存读取统一复用该入口，避免同类问题再次出现。
3. 修复后，工单 AI 分析页面会继续展示 Agent/Worker 的真实失败原因，便于直接排查模型、命令或环境问题。

## 影响范围

- 工单 AI 分析通过本机 Agent 网关等待结果的场景。
- Agent AI 分析结果命中 Redis 缓存后的重复读取场景。

## 用户侧变化

如果 Worker 实际失败，页面会显示真实失败摘要，而不再被 `Cannot check isinstance when validating from json` 这类框架异常覆盖。
