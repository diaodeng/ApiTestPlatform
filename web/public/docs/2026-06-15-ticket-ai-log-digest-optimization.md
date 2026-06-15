# 工单 AI 日志整包分析摘要优化

## 背景

工单 AI 分析支持日志整包模式：当日志拉取未配置开始/结束时间时，服务端不会把几十 MB 日志正文放进请求体，而是下发压缩包地址；`client_new` Agent 下载并解压到任务工作区，再由 Codex 读取本地文件分析。

该方式避免了服务端请求体过大，但如果 prompt 直接要求 Codex 读取 `source_logs/`，模型可能扫描多个 10MB 级日志文件，实际 token 消耗仍然不可控。

## 本次调整

- Agent 解压整包日志后，会先生成 `logs_ai_digest.txt`。
- 摘要按工单标题、描述、日志提示和通用支付/异常关键词筛选日志片段。
- 默认最多写入约 300000 字符，保留文件名和行号，便于 Codex 必要时定点回查原始日志。
- 服务端和 Agent prompt 均调整为优先读取 `logs_ai_digest.txt`；只有摘要证据不足时，才按摘要中的文件名和行号读取 `source_logs/` 原始日志。
- 完整压缩包和解压日志仍保留在工作区，不影响人工复核和模型二次定点检索。

## 影响范围

- `client_new/services/ticket_ai_analysis_service.py`
- `server/modules/ticket/service/ticket_ai_analysis_service.py`

## 当前链路说明

1. 服务端构建 `sourceLogPull`，如果日志记录没有入库正文，会设置 `wholeArchiveMode=true` 并下发 `commandResultUrl/storagePath`。
2. Agent 写入 `logs.txt` 作为整包分析说明。
3. Agent 下载并解压压缩包到 `source_logs/`。
4. Agent 生成 `logs_ai_digest.txt` 和 `source_logs_manifest.json`。
5. Codex 优先读取摘要文件进行分析，避免默认通读完整日志包。

## 建议

能明确时间范围时，仍建议在日志拉取时填写开始/结束时间或时间点前后范围，让系统只入库关键片段。整包模式适合没有明确时间范围或需要本地留存完整日志包的场景。
