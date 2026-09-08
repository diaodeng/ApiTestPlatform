# 2026-09-08 Agent孤儿租约清理与AI回传协议瘦身

## 背景

2026-09-08 10:35 生产 fastapi 进程再次被 cgroup OOM Kill（第 3 次，`oom_kill` 计数经前日修复的 cgroup v1 采集首次实录为 1）。同时两个工单（INC00001934853 / INC00001933577）重试后"一直 AI 分析中"约 24 分钟。

排查确认两个问题：

1. **孤儿租约阻塞队列**：进程被杀时等待 Agent 响应的协程随进程死亡，但 Redis `agent:ai_analysis:active` 里的运行租约（lease 3900 秒）仍占着唯一并发槽位；重启后的重试请求只能排队等旧租约自然过期，实测阻塞 24 分钟（10:38 重试 → 10:59:36 租约到期后队列自愈）。
2. **Agent 回传体过大**：量化 Redis 结果缓存证实，Agent 回传响应中 `result.raw_output`（完整 worker stdout）占 8068KB / 8086KB（99.7%），而真正需要的 `analysis_result` 仅 17KB。该 8MB 体经 WebSocket 分片接收 + JSON 序列化 + 响应模型驻留叠加出百 MB 级内存峰值，正是 OOM 的直接诱因（10:30-10:32 连续 5 次工单同步 AI 处理后 10:35 被杀）。

## 变更内容

### 1. 孤儿租约启动清理（`server`）

- `AgentDispatchService.cleanup_orphan_active_leases(redis)`：服务启动阶段清空所有 Agent 的 `active` 租约并按请求标记 `status=failed, reason=orphan-lease-cleanup-on-restart`。启动时刻不可能存在真正运行中的请求（请求只由本进程发出），清空安全；Agent 若在重启期间完成执行，结果由既有迟到结果缓存机制恢复，不依赖租约。
- 启动钩子接入：`startup_handler(app)` 在 `app.state.redis` 就绪后调用 `cleanup_orphan_agent_leases(app)`，清理异常只记日志不阻塞启动。
- 效果：重启后重试请求从"等旧租约过期（最长 65 分钟）"变为**秒级获得槽位**。
- 实现细节：SCAN 游标循环（兼容 MemoryRedis 测试后端，它只有 `scan` 没有 `scan_iter`）；`_serialize_state` 支持 `message.extra` 透传诊断字段。

### 2. AI 回传协议瘦身（`client_new` + `server` 兜底）

- **Agent 客户端**（`client_new/services/ticket_ai_analysis_service.py`）：两处回传点（真实执行 + 缓存命中）的 `result.raw_output` 从整包 stdout 截断为头部 8000 字符（`RAW_OUTPUT_SUMMARY_CHARS=8000`），完整内容留在本地 `worker.stdout.txt`（`stdout_path` 字段本就回传路径）。回传体从 4-8MB 降至约 30KB。
- **服务端兜底**（`ticket_ai_analysis_service.py`）：新增 `_truncate_response_raw_output`，在响应接收入口（`_process_task` 解析 `response_object` 后立即执行）就地截断超长 `raw_output`（`RESPONSE_RAW_OUTPUT_MAX_CHARS=8000`），兼容尚未升级的旧版 Agent。截断只影响服务端驻留与审计摘要，不影响 `analysis_result` 解析与写回。
- 失败诊断不受影响：`_resolve_agent_failure_message` 优先使用结构化 `error_message`/`message`，8KB 头部摘要足够 `_summarize_worker_error` 提取失败原因。

## 变更文件

- `server/module_qtr/service/agent_dispatch_service.py`：`cleanup_orphan_active_leases` + `_serialize_state` 支持 extra
- `server/module_qtr/controller/agent_controller.py`：`startup_handler(app)` + `cleanup_orphan_agent_leases`
- `server/server.py`：lifespan 调用改为 `startup_handler(app)`
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：`_truncate_response_raw_output` + 接入点
- `server/tests/test_agent_dispatch_service.py`：+3 测试（清理/空场景/队列恢复回归）
- `server/tests/test_ticket_ai_task_status.py`：+4 测试（dict/模型截断/短文本保留/容错）
- `client_new/services/ticket_ai_analysis_service.py`：两处回传点瘦身 + 类常量

## 验证

- pytest：`test_agent_dispatch_service.py` 8 用例（含"OOM 重启后队列立即恢复"回归场景）、`test_ticket_ai_task_status.py` 截断 4 用例，连同 embedding/metrics/similarity 等相关套件共 87 用例全部通过。
- ruff：所有改动文件通过；`client_new` 文件的 17 个存量告警经 git stash 基线对比确认非本次引入。
- 未执行项：真实 OOM 重启演练（需部署后观察下一次重启的恢复日志 `服务重启清理遗留 Agent 运行租约` 与重试排队时间）；双端需同时发版才能完整生效（服务端兜底保证仅发服务端也安全）。

## 剩余风险与建议

- 容器内存 1.4GB → 2GB 仍未落地，这是第 3 次 OOM 后最紧迫的运维操作。
- 诊断快照（页面可视化配置）建议保持开启观察 v636 版本的内存水位。
