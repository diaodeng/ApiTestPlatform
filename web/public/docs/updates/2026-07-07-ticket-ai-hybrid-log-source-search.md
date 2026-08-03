# 2026-07-07 工单 AI hybrid 日志模式强制检索原始目录

## 背景

用户反馈发起工单 AI 分析时选择“摘要 + 完整目录”（`hybrid`），但 Agent 实际分析容易停留在 `logs_ai_digest.txt` 摘要层，没有充分检索 `source_logs/` 原始日志目录，导致大日志包中未被摘要命中的异常被遗漏。

## 调整内容

1. 服务端下发的工单 AI prompt 中，`hybrid` 模式从“先看摘要再复核关键证据”调整为：
   - 摘要只作为定位索引；
   - 必须查看 `source_logs_manifest.json` 或列出 `source_logs/` 文件清单；
   - 必须至少对 `source_logs/` 执行一次 `rg` 关键词检索；
   - 最终证据尽量引用原始日志文件路径和行号，不只引用 `logs_ai_digest.txt`。
2. `client_new` Agent fallback prompt 同步调整，避免服务端 prompt 为空或历史任务重建时语义不一致。
3. `logs_ai_digest.txt` 文件说明同步区分 `digest` 与 `hybrid`：`digest` 可优先基于摘要分析，`hybrid` 下摘要仅用于定位，仍必须检索原始日志目录。
4. 新增后端单元测试，锁定 `hybrid` prompt 必须包含完整目录检索要求。

## 与上下文长度的关系

- 当前服务端写入 AI 上下文的日志正文 `sourceLogPull.text` 默认按首尾保留截断到 `800000` 字符。
- 当前 `client_new` 生成的 `logs_ai_digest.txt` 摘要最大为 `300000` 字符。
- `source_logs/` 是解压后的原始日志目录，不会因为上述两个文本上限被删除；`hybrid` 的问题主要是模型执行策略停在摘要层，而不是目录不存在。
- 使用第三方 OpenAI 兼容 Provider 时，是否因上下文过长失败取决于所选模型和网关的上下文窗口。项目侧仍需要避免把完整日志正文直接塞进 prompt，推荐通过 `rg` 检索原始目录按需读取。

## 验证

- `uv run python -m unittest tests.test_ticket_ai_analysis_prompt`

