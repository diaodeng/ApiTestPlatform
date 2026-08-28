# 工单深度 AI 分析说明

## 功能

工单详情页的“发起 AI 分析”用于结合工单、时间线、日志和指定版本仓库生成根因分析、证据、风险和处理建议。任务由本机 Agent 执行，服务端负责结果校验和写回工单。

入口：工单详情页 → AI 区域 → **发起 AI 分析**。提交后可在“任务历史”查看状态、执行 Agent、模型、工作区和错误信息。

## Provider 与执行器

- Codex：结果从任务工作区的 `result.json` 读取。只有 Worker 退出码为 `0`、结果 JSON 可解析且通过本次任务的 JSON Schema 时才算成功。
- Claude Code：使用命令输出的 JSON，优先读取 `structured_output`，其次解析 `result` 最终文本；`is_error=true` 或进程执行失败时算失败。
- Worker 的 `stderr` 可能包含正常进度、模型输出和诊断信息。`stderr` 非空本身不会使 Codex 分析失败。
- Worker 失败时，任务会记录结构化的“错误码”和真实“错误信息”；失败响应不包含工单正文或分析结果。`workerExitCode` 仅用于辅助诊断，不能替代业务错误码。
- Schema 兼容接口中按字符串传输的 BIGINT ID，并包含 `symptom`、`similar_cases`、`sop_suggestion`、`owner_suggestion`、`monitoring_suggestion` 等可选增强字段；字段缺省时由服务端补默认值。

## 请求幂等

服务端会根据以下输入生成分析请求指纹：

- 工单、版本和日志来源记录；
- 仓库映射、仓库地址和分支；
- 最终提示词和输出 Schema；
- Provider、模型、执行器和 Agent；
- 日志分析模式、时间窗口策略和 resume 选项。

同一指纹已有成功任务时，重复提交或点击重试会直接返回原成功结果，不重新调用 Agent，也不会重复写入 AI 消息、RCA、快照和事件。失败任务不占用成功结果唯一记录，因此可以继续重试。对尚未写回成功结果、但任务工作区已经有有效 `result.json` 的重试，会使用新的 Agent 网关请求 ID，并由本机 Agent 直接复用该文件，不重新启动 Worker。

启用“强制刷新”会生成新的请求指纹并重新分析。只有在日志、版本、提示词或模型等输入确实发生变化，或明确需要重新分析时才建议使用。

## 工作区与代码仓库

每次任务使用独立目录：

```text
<工作区根目录>/ticket_<工单ID>/task_<任务ID>/
```

该目录保存 `ticket.json`、`timeline.json`、`context.json`、提示词、结果和 Worker 日志。Codex 会把当前任务目录作为主项目并自动加入 trusted，代码仓库使用指定目录下的 Git worktree 作为额外可写目录。不会自动信任整个磁盘、用户目录或仓库父目录。

Codex 使用 `workspace-write` 沙箱和自动审批参数运行，适用于后台分析任务；这不等同于关闭操作系统 UAC，也不应改成 `dangerously-bypass-approvals-and-sandbox`。

## 常见问题

### 任务显示失败，但日志中有分析内容

先查看任务工作区的 `result.json`、`worker.stdout.txt` 和 `worker.stderr.txt`。如果 Codex 退出码为 `0` 且结果符合 Schema，重试会复用该任务工作区中的有效结果；如果 JSON 内容损坏、字段类型错误或缺少必填字段，仍需重新分析。

### 为什么重复点击没有产生新任务

这是请求幂等的正常表现。只要输入指纹一致且已有成功结果，系统会返回历史成功任务，避免重复消耗模型调用并避免重复写回。

### 为什么强制刷新后任务ID变化

强制刷新明确要求绕过历史成功结果，因此会创建新的任务和新的请求指纹；旧结果仍保留在任务历史中。

### 如何判断 AI 分析失败

服务端以任务响应中的 `success` 和 `status` 判断执行状态：`success=false` 或 `status=failed/timeout` 表示失败，不再通过工单正文、分析结果文本或日志中的普通 `Error:` 关键字推断失败。

失败任务可查看以下字段：

- `errorCode`：稳定的业务错误码，例如 `AI_PROVIDER_QUOTA_EXCEEDED`、`AI_PROVIDER_AUTH_FAILED`、`AI_WORKER_PERMISSION_DENIED`。
- `errorMessage`：Provider 或 Worker 返回的真实异常信息。
- `workerExitCode`：本地进程退出码，仅作为辅助信息。

如果 Worker 同时出现本地诊断告警和 Provider 致命异常，Provider 致命异常作为主错误保存，本地告警只保留在 Agent 诊断日志中。
