---
title: 工单 AI 分析 Token 用量统计修复
---

# 工单 AI 分析 Token 用量统计修复

## 变更内容

- Codex Worker 执行命令新增 `--json` 参数：stdout 输出 JSONL 事件流，其中 `turn.completed` 事件携带每回合的 Token 用量（`input_tokens`、`cached_input_tokens`、`output_tokens` 等）。
- Token 用量在 Agent 客户端本地解析统计，仅最终汇总值随结果回传服务端入库；过程事件流不上传。
- Agent 客户端新增 JSONL 事件流解析：逐行累加所有 `turn.completed` 事件的用量，得到本次任务整个过程的总消耗，而不是只取最后一次的值。
- Claude Code 链路同步支持：从结果 JSON 的 `modelUsage` 按模型逐个累加（覆盖主模型和辅助小模型），无 `modelUsage` 的旧版本回退顶层 `usage` 近似值。
- Codex 与 Claude 的解析逻辑按报文特征双向隔离（`turn.completed` 事件流 vs `type=result` 单行 JSON），互不误判。
- 分析结果与 Token 用量分别回传：结果本体仍从 `result.json` 读取，`token_usage` 字段随成功响应返回，并写入 `result` 对象。
- Agent 网关响应模型 `AgentResponseWebUI` 新增 `token_usage` 字段，修复 Pydantic 校验静默丢弃该字段导致服务端始终拿不到用量的问题。
- 服务端按原逻辑归一化入库：任务记录写入 `input_token_count`、`output_token_count`、`total_token_count`；审计执行记录写入 `token_usage` 明细。

## Token 统计口径

- Codex `input_tokens`：所有回合的输入 Token 累加（包含缓存命中部分）；Claude 按 `modelUsage` 各模型 `inputTokens` 累加。
- `output_tokens`：Codex 按回合累加；Claude 按模型累加（包含辅助模型的输出）。
- `cached_input_tokens`：缓存命中明细累加（Codex 的 `cached_input_tokens`、Claude 的缓存读写），仅审计展示，不计入总量避免重复。
- `total_tokens`：输入 + 输出累计；Codex 若出现缓存大于输入的口径差异，按缓存 + 输出兜底。

## 注意事项

- Codex 事件流中无独立的 `total_tokens` 字段，总量由客户端按上述口径计算。
- Claude 顶层 `usage` 是主模型最后一次 API 调用的值（非任务累计），统计以 `modelUsage` 累加为准。
- 历史任务的 Token 统计仍为 0，修复后新执行的任务才会记录真实用量。
- Token 统计失败不影响分析结果：解析不到用量时回传 `null`，任务照常成功。
