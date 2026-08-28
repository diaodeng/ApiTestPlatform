# 2026-08-28 工单 AI 结果判定与幂等

- Codex 分析成功改为同时要求退出码为 `0`、结果 JSON 可解析并通过 Schema；`stderr` 非空不再作为失败条件。
- 保留 Claude Code 对 `structured_output`、最终 `result` 和 `is_error` 的专用解析方式。
- 增加分析请求指纹和成功结果唯一约束；重复提交或重试命中成功结果时不重新分析，也不重复写入消息、RCA、快照和事件。
- Codex 任务以当前任务工作区作为可信主项目，指定 Git worktree 通过受控额外目录提供，不扩大 trusted 范围。
- 同一任务的每次 Agent 执行尝试使用不同的网关请求 ID，避免重试命中旧的失败响应缓存；Agent 命中有效 `result.json` 时直接返回，不重新启动 Worker。
- 修正结果 Schema 与实际 Agent 输出不一致的问题：兼容 BIGINT 字符串、文本型置信度和可选协同增强字段，已有有效结果文件可在重试时直接校验并写回。
