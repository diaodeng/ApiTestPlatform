# 2026-06-22 工单 AI 日志分析模式与时间窗口兜底

## 背景

工单 AI 分析原先在整包日志模式下默认由 Agent 生成 `logs_ai_digest.txt` 摘要，Codex 优先读取摘要再定点查看原始日志。该模式适合控制上下文和执行成本，但在排查 `MemoryError`、`OOM` 等偶发异常时，可能因为摘要关键词、文件命中上限或时间窗口不完整导致漏证据。

## 本次调整

1. 新增工单 AI 日志分析模式：
   - `digest`：生成摘要，保持原默认行为。
   - `full_directory`：不生成摘要，只解压整包日志并告诉 Codex `source_logs/` 目录，由 Codex 自行检索分析。
   - `hybrid`：生成摘要，同时允许 Codex 读取完整 `source_logs/` 复核证据。
2. 新增时间窗口缺失策略：
   - `agent_extract`：数据库没有对应截取正文时，将整包下发 Agent，由 Agent 在本地按时间窗口截取。
   - `server_extract`：发起 AI 分析时由服务端基于归档包实时截取时间窗口。
3. 系统管理 -> AI 配置中心 -> AI 分析 Worker 配置新增全局默认：
   - 日志分析模式。
   - 窗口缺失策略。
4. 工单详情 -> 发起 AI 分析新增本次覆盖配置：
   - 日志模式。
   - 日志时间：不指定、开始/结束、时间点前后。
   - 缺失策略。

## 执行说明

- 默认值仍为 `digest + agent_extract`，老请求不传新字段时保持原行为。
- `full_directory` 模式下 Agent 仍会下载并解压日志包，写入 `source_logs_manifest.json`，但不会生成 `logs_ai_digest.txt`。
- 时间窗口模式下若数据库没有已截取正文，`agent_extract` 会在 Agent 侧按 `requestedBeginTime/requestedEndTime` 截取并写入 `logs.txt`。
- prompt 已明确要求内存问题检索 `MemoryError`、`OOM`、`OutOfMemory`、`out of memory`、`heap`、`GC overhead`、`内存不足` 等关键词。

## 风险

- `full_directory` 会把更多检索工作交给 Codex，超大日志包可能增加执行耗时。
- `server_extract` 依赖服务端能访问归档包或外部下载地址，否则会回退为任务上下文中的缺失提示。
- Codex 的文件读取仍受 CLI sandbox 和 `-C` 工作目录影响；当前日志目录位于任务工作区，prompt 使用绝对路径提示读取。
