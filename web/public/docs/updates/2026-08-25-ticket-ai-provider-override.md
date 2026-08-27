# 工单 AI 分析 Provider 下发修复

## 修复内容

- 修复工单 AI 分析选择 Claude Code 或 Codex Provider 后，Worker 仍可能使用 `workerEnv` 或任务工作区旧配置的问题。
- 当前选中 Provider 的 API Key、基础地址和模型会覆盖同名 `workerEnv` 配置。
- Codex 任务级 `config.toml` 支持带缩进的 `base_url` 配置覆盖。
- Claude Code 任务工作区 `.env` 在重试或切换 Provider 时会覆盖旧的 API Key 和基础地址。

## 并发配置

Agent 工单分析并发限制位于“系统管理 → AI 配置中心 → Agent 并发数”，配置键为 `ticket.ai.agent.maxConcurrentTasks`，默认值为 `1`。单个 Agent 达到上限后，新任务进入队列等待。

## 注意事项

Provider 的密钥不会写入普通日志；排查时应查看任务工作区的 Worker 日志和脱敏鉴权诊断信息。
