# 2026-05-26 工单 AI 分析 WebSocket loop 亲和修复

## 背景

工单 AI 分析在点击重试后，服务端日志已经收到完整 Agent 响应，但任务状态仍停留在“进行中”。

## 根因

`server/module_qtr/service/agent_service.py` 在后台线程中通过 `asyncio.run(...)` 发起 Agent 请求时，会创建临时事件循环；如果直接用这个临时 loop 去发送 WebSocket 分片，或在另一个 loop 上直接调用 `future.set_result()` / `future.cancel()`，就会出现 loop 归属错误。

这会导致两类症状：

- 重试场景下，Agent 已回包但任务仍停留在“进行中”。
- 发起分析场景下，发送分片时报 `got Future attached to a different loop`。

## 修复

- 在 `response_futures` 中保存 Future 所属事件循环。
- 发送 Agent 请求时，统一切回 Agent WebSocket 所属事件循环执行。
- 回写响应时使用 `loop.call_soon_threadsafe(future.set_result, response_data)`。
- 断连或清理时同样使用线程安全方式取消 Future。

## 影响范围

- 工单 AI 分析任务重试与首次提交。
- Agent WebSocket 响应回写链路。

## 验证建议

- 重新提交一个 AI 分析任务，确认日志出现 `Agent 请求完成` 后，任务状态从 `running` 变为 `success` 或 `failed`。
- 在重试场景下确认任务不再长期停留在“进行中”。
