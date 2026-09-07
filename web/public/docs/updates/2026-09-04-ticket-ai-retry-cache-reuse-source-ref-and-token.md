# 2026-09-04 工单AI分析重试复用缓存：来源引用修复与Token重复计入优化

## 问题背景

工单 INC00001920244 在 prod 环境第一次 AI 分析（审计ID 2046320370764800）实际已真实跑完模型（Worker 执行 680 秒），但因结果 schema 校验失败 + Agent 端变量未定义崩溃（见 2026-09-03 更新记录），任务以失败终态落库，且失败审计记录里保留了本次真实消耗的 token。

问题修复后重试同一任务，Agent 命中本地工作区缓存 `result.json` 直接回传成功（审计ID 2046582534749184）。此时用户在「AI 执行审计」中发现两个异常：

1. 同一工单两条审计记录的「来源引用」不一致：失败记录显示 `INC00001920244`，重试成功记录显示 `2046301627784192`（纯数字系统工单ID）。
2. 两条记录都有完全相同的 token 用量：同一次真实模型消耗被失败审计和缓存成功审计各记了一遍，Token 统计翻倍。

## 问题现象与根因

### 来源引用不一致

服务端为工单 AI 分析创建审计记录时，`source_ref` 的取值口径在两处不一致：

- 首次创建（`_ensure_task_execution_record`）：`ticket.ticket_no or str(task.ticket_id)`，显示业务工单号 INC00001920244；
- 重试新建尝试记录（`retry_analysis_task_services`）：`str(task.ticket_id)`，直接写系统工单ID 2046301627784192。

重试记录的来源引用因此从 INC 编号变成了纯数字 ID。

### Token 重复计入

Agent 缓存命中时（`client_new/services/ticket_ai_analysis_service.py` 的缓存分支）会尽力"恢复"历史 token：优先读结果文件内嵌 usage，否则从落盘的 stdout 事件流解析，并随响应回传给服务端。该设计本意是让真实消耗可追溯，但服务端把这份"历史消耗"当成了本次调用的消耗：

- 写入本次任务表的 `input/output/total_token_count`，历史列表和概览直接读取；
- 写入本次审计记录的 `token_usage`。

于是同一次真实消耗在「失败审计记录」和「缓存成功审计记录」各出现一次，任务表也重复累计，任何按记录求和的 Token 统计都会虚高。

## 修复内容

### 来源引用统一（服务端）

`retry_analysis_task_services` 新建重试审计记录时，`source_ref` 改为与首次创建同一口径：优先业务工单号，工单号缺失时才回退系统工单ID。此后重试审计与首次审计的来源引用一致显示 INC 编号。

### Token 重复计入优化（服务端 + Agent 端）

设计原则：**每一次真实模型调用只允许对应一份 token 记录**。缓存命中不是一次真实调用，本次审计不应再带 token。

1. **Agent 端回传缓存命中标记**：缓存命中分支的响应新增 `cache_hit: true` 字段（真实执行不带该字段）。恢复出的 token 仍随响应回传（保持可追溯），但服务端不再据此入库。
2. **服务端识别并剔除**：成功写回时检测 `cache_hit`（响应对象 / 外层响应 / result 载荷任一携带即命中；同时兼容旧版 Agent——result 内 `command_line == "cached:result.json"` 也视为缓存命中，无需等 Agent 重新发版）：
   - 命中时不把 token 写入任务表统计字段（`input/output/total_token_count` 保持空）；
   - 命中时不把 token 写入本次审计记录（`token_usage` 为空）；
   - 任务状态描述改为「复用 Agent 缓存结果」，明确提示用户本次没有重新跑模型。
3. **服务重启恢复链路同口径**：`_process_recovered_success`（恢复迟到结果写回）同样检测缓存命中，命中时任务状态为「复用 Agent 缓存结果（恢复服务重启前的执行结果）」，且不写 token。

### 与既有复用审计的关系

页面点重试但任务已成功时走的 `status=reused` 轻量复用事件（不发起任何调用）此前已存在；本次修复覆盖的是另一条路径——重试真实派发到 Agent、Agent 用本地缓存结果返回成功的情况。两条路径现在都满足"复用不重复计 token"。

## 生效说明

- 服务端改动重启后端即生效（含对旧版 Agent 的 `cached:result.json` 兜底识别）。
- Agent 端 `cache_hit` 标记需重新打包客户端后生效；未更新期间靠服务端兜底逻辑识别，行为一致。

## 验证

- `uv run pytest tests/ -q -k "ticket_ai"`：43 个用例全部通过。
- `uv run ruff check`：服务端改动文件全部通过（client_new 文件存在历史遗留的 import 排序告警，与本次改动无关）。

## 涉及文件

- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py` — 重试审计 source_ref 统一；主执行链路与迟到恢复链路的缓存命中识别、token 剔除、状态描述。
- `server/module_qtr/service/agent_service.py` — `AgentResponseWebUI` 新增 `cache_hit` 字段。
- `client_new/services/ticket_ai_analysis_service.py` — Agent 缓存命中响应回传 `cache_hit: true`。
