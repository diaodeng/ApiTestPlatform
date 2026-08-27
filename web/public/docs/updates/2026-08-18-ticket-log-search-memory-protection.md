---
title: 工单日志搜索内存保护
type: update
source_type: mixed
updated: 2026-08-18
---

# 工单日志搜索内存保护

## 变更内容

工单日志搜索新增两个资源保护配置：

- `maxConcurrentSearches`：单进程同时执行的搜索数，默认 2，范围 1-8。
- `maxSearchLineBytes`：单条搜索结果的最大 UTF-8 字节数，默认 524288（512 KiB），范围 1024-4194304。

rg 搜索最终输出使用 `--max-columns --max-columns-preview` 限制超长行，用户设置的结果条数 `limit` 仍然动态生效。搜索结果按行流式解析，不再先将整个 rg 输出和拆分后的行列表同时加载到 Python 内存。

搜索接口不再额外执行固定 500 字符预览复制。超长命中行通过 `contentTruncated` 标记，查看完整内容时继续使用日志行内容或上下文接口按文件和行号读取。

## 注意事项

- `maxSearchLineBytes` 限制的是搜索响应中的单行字节数，不是搜索文件扫描总量，也不是用户选择的命中行数。
- Python 降级搜索同样使用该单行限制；文件扫描总量仍由 `maxPythonSearchBytes` 控制。
- 并发限制是单进程限制，多副本部署时每个副本分别生效。
