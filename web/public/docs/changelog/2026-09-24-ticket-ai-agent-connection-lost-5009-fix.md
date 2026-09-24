# 2026-09-24 - AI 分析连接中断误判失败修复（418→5009）与客户端独立心跳

## 问题现象

工单 AI 分析任务在 Agent 连接中断时被直接判为终态失败（`AI_AGENT_TRANSPORT_ERROR`），任务错误消息显示为无意义的 `()`。实际 Agent 侧 Worker 仍在后台正常执行并完成了分析，结果无法写回，只能人工重试；若在 Redis 迟到结果缓存过期（24 小时）后重试，审计上也缺少直接佐证。实战案例：工单 00009930（2026-09-23 21:56），服务端心跳判定离线主动断连，Worker 22:22 完成的迟到结果最终未被消费。

## 根因

1. **状态码错配**：Agent 网关在连接中断（心跳判定离线、断连清理、会话接管）时取消等待中的响应 Future，触发 `asyncio.CancelledError`，网关返回 `TASK_CANCELLED(418)`。工单服务只把 `AGENT_CONNECTION_LOST(5009)` 识别为"连接中断、进入恢复等待"，418 落入通用失败分支，任务被提前置为终态失败，已有的迟到结果补交机制（pending_recovery → 恢复扫描 → 自动写回）完全没有被触发。
2. **空错误消息**：`except` 分支统一使用 `str(e.args)` 生成错误消息，`CancelledError` 等空参数异常渲染为 `"()"`，排查时无法定位；同时 `logger.error(e)` 对空消息异常只打出一个空行。
3. **Python 3.10 超时分支失效**：`except TimeoutError` 在 Python 3.10 下接不住 `asyncio.wait_for` 抛出的 `asyncio.TimeoutError`（两者 3.11 才合并），真超时会掉进 `except Exception` 产生同样的 `"()"` 消息和 500 状态码。
4. **心跳单点依赖（非对称故障防误杀）**：客户端只在收到服务端 ping 时才被动回 pong，自己从不主动上报。server→client 单向断（NAT 会话老化、防火墙状态表单向过期等有状态中间设备场景，TCP 并非两方向必然同时断）时 pong 永远不会触发，服务端因收不到任何消息误判离线并杀连接——而 client→server 方向（AI 结果、事件上报的实际回传方向）是健康的，属于误杀。

## 修复方式

### 服务端 `server/module_qtr/service/agent_service.py`（`_send_message_on_agent_loop`）

1. **CancelledError 分支改为返回 5009**，消息改为固定可读文案（含 agent_code 与 request_id）。该分支只可能由连接级清理触发（用户取消任务走 cancel_task 消息通道，不取消等待 Future），因此可以无条件映射；工单侧据此进入 pending_recovery 等待 Agent 补交结果，超期（timeout + 15 分钟）由恢复扫描任务兜底置败。
2. **超时捕获改为 `except (TimeoutError, asyncio.TimeoutError)`**，覆盖 Python 3.10 的 `asyncio.TimeoutError`，保证真超时始终返回结构化的 407 响应；并补齐未知 request_type 的超时兜底返回。
3. **空 args 异常消息回退类型名**：`e.args` 为空时使用 `type(e).__name__`，日志与错误消息不再出现 `"()"`。

### 客户端 `client_new/server/agent_server.py`

4. **新增独立周期心跳**：连接建立时启动 `_proactive_heartbeat_loop`，每 30 秒（`HEARTBEAT_INTERVAL`）主动向服务端发送一次 pong，不再依赖服务端 ping 被动触发；连接退出时随看门狗一并停止，重连成功后重新启动。服务端接收循环在解析消息类型前就刷新 `heart_time`，主动心跳自然计入，服务端无需改动。响应消息类型仍为 `pong`，与既有协议完全兼容。

## 变更文件

- `server/module_qtr/service/agent_service.py`
- `client_new/server/agent_server.py`

## 验证结果

- `uv run ruff check` 与 `py_compile` 通过（服务端两文件、客户端 agent_server.py）。
- Agent 相关既有测试全部通过：`test_agent_dispatch_service.py`、`test_ticket_ai_handle_response_transport.py`（14 passed）、`test_agent_chunk_registry.py`、`test_agent_connection_session.py`（9 passed）。
- 行为验证（临时脚本，已删除）：
  - 等待 Future 被取消（复现断连清理场景）→ 返回 5009 + 明确文案；
  - 空 args 异常 → 消息为 `RuntimeError` 而非 `()`；
  - `asyncio.TimeoutError` → 返回 407 超时响应。

## 部署说明

- 服务端改动需部署到网关所在服务器（testautoapi）后重启生效；客户端改动随新客户端版本分发。
- 未做：孤儿迟到结果反查拉起历史任务（评估为有僵尸任务风险且修复后价值有限，暂不实施）；本修复不自动恢复已终态失败的历史任务。

## 剩余风险

- 断连后进入 pending_recovery 的任务恢复等待期最长约 75 分钟（timeout 3600s + 900s），期间任务列表显示"等待 Agent 补交结果"，属预期行为。
- 独立心跳与服务端 120 秒离线判定之间无联动调整；若未来服务端心跳判定收紧（小于 30 秒），需同步调整客户端心跳间隔。
