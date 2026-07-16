# 2026-07-16 工单日志搜索耗时观测补充

## 结论

本次只补充后端日志埋点，不改变日志准备、解压、搜索和上下文读取策略。

## 背景

2026-07-15 日志搜索曾做过资源保护优化：

1. 准备阶段增加解压耗时、文件数和总字节数保护。
2. 搜索阶段曾从整目录一次性执行 `rg` 调整为按文件执行 `rg`，该策略在文件数较多时会放大进程启动成本。
3. 当前已改为在 `maxSearchFileCount` 限制内一次性交给 `rg` 搜索；多关键字 `all` 使用 `rg` 管道流式过滤，中文关键字同样优先走 `rg`。

因此若日志目录中文件数较多，重点观察 `target_file_count`、`tool`、`search_mode`、`with_context` 和 `elapsed_ms`，确认耗时来自文件扫描、上下文读取还是 Python 降级。

## 本次补充

1. `/ticket/logs/prepare` 对应的 `LogService.prepare` 增加日志：
   - `ticket_id`、`record_id`
   - 原始归档位置 `archive_path`
   - 服务端缓存压缩包位置 `source_path`
   - 解压目录 `extract_path`
   - 识别到的日志文件数量 `file_count`
   - 准备耗时 `elapsed_ms`

2. `/ticket/logs/search` 对应的 `LogService.search_keywords/search` 增加日志：
   - 使用工具 `tool=rg/python`
   - 搜索目录 `extract_dir`
   - 指定文件 `file` 或全目录 `<all>`
   - 扫描文件数 `target_file_count`
   - 关键字 `keywords` 和匹配模式 `search_mode`
   - 上下文参数、返回上限、是否带上下文
   - `rg` 可执行文件和核心参数，或 Python 降级原因
   - 命中数 `hit_count` 和搜索耗时 `elapsed_ms`

## 排查建议

1. 若 `target_file_count` 很大，优先使用“在此文件搜索”缩小范围。
2. 若日志显示 `tool=python`，重点看是否是环境变量强制 Python、服务器缺少 `rg` 或 `rg` 执行异常；中文关键字和 `all` 模式不应再默认触发 Python。
3. 若 `with_context=true` 且命中较多，耗时包含上下文行索引构建和读取成本，可先关闭上下文确认纯搜索耗时。
