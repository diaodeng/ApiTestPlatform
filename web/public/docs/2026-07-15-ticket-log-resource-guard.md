# 2026-07-15 工单日志拉取查看资源保护

## 结论

- 工单日志查看准备、关键字搜索和原始归档实时截取已补齐资源保护，降低大日志包导致应用卡顿、线程占满或进程被重启的风险。
- 保护阈值统一读取系统参数 `ticket.logPull.storage`，不在日志搜索页面额外展示文件数量；需要调整时在参数配置中维护。
- 日志入库内容重新启用 `maxContentChars` 上限，超过上限会失败并提示缩小时间范围。

## 配置项

`ticket.logPull.storage` 新增以下运行保护字段：

| 字段 | 默认值 | 作用 |
|---|---:|---|
| `maxExtractSeconds` | 300 | 日志查看准备阶段最大解压秒数 |
| `maxExtractFileCount` | 2000 | 日志查看准备阶段最大解压文件数 |
| `maxExtractTotalBytes` | 2147483648 | 日志查看准备阶段最大解压总字节数 |
| `maxSearchSeconds` | 30 | 日志关键字搜索最大执行秒数 |
| `maxSearchFileCount` | 1000 | 日志关键字搜索最大扫描文件数 |
| `maxPythonSearchBytes` | 268435456 | 非 ASCII 或无 `rg` 时 Python 降级搜索最大扫描字节数 |

## 实现要点

1. `LogService.prepare(...)` 读取存储配置后，在复用既有解压目录和递归解压过程中检查耗时、文件数和总大小。
2. `LogService.search(...)` 不再一次性对整个目录执行 `rg` 并收集全部输出，而是按文件执行、按剩余命中上限 `-m` 截断，并用 `maxSearchSeconds` 控制总耗时。
3. Python 降级搜索会按 `maxPythonSearchBytes` 限制总扫描字节数，避免中文关键字或无 `rg` 环境下全量扫大目录。
4. 文本文件识别只读取文件头部 8KB 样本，不再把未知后缀的大文件整体读入内存。
5. 原始归档实时截取返回前会把 gzip+base64 内容解压成普通文本，避免前端收到压缩串；同时继续受 `maxContentChars` 约束。

## 影响范围

- 后端接口：`/ticket/logs/prepare`、`/ticket/logs/search`、`/ticket/logs/search_time`、`/ticket/logs/errors`、`/ticket/log-pulls/{record_id}/content`。
- 前端页面不新增文件数量展示；搜索超过保护阈值时会收到后端失败提示。

## 验证

- `cd server; uv run python -m py_compile modules/ticket/service/log_pull/ticket_log_service.py modules/ticket/service/log_pull/ticket_log_pull_service.py modules/ticket/controller/ticket_log_pull_controller.py modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `cd server; uv run ruff check modules/ticket/service/log_pull/ticket_log_service.py modules/ticket/service/log_pull/ticket_log_pull_service.py modules/ticket/controller/ticket_log_pull_controller.py modules/ticket/entity/vo/ticket_log_pull_vo.py`
