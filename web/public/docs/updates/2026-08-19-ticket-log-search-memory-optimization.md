---
title: 工单日志搜索内存优化
type: update
source_type: mixed
updated: 2026-08-19
---

# 工单日志搜索内存优化

## 变更内容

针对多次搜索不同工单日志后内存持续增长、最终导致应用重启的问题，进行以下优化：

### 页缓存释放

- 每次 rg 搜索完成后，对已搜索的日志文件调用 `posix_fadvise(POSIX_FADV_DONTNEED)` 建议 OS 释放页缓存。
- 仅 Linux 生效，Windows 跳过，不影响功能。
- 日志文件本身保留在磁盘上，仅释放 OS 对文件数据的缓存。

### 移除冗余的 Python 侧命中校验

- rg 管道链已通过 `--fixed-strings`、`-e` 多关键字和逐级过滤确保最终输出行满足匹配条件，不再需要 Python 侧 `_match_keywords` 二次校验。
- 前端不使用 `matched_keywords` 按命中粒度高亮，后端统一传入所有关键字。
- 移除 `_parse_rg_line` 中对 rg 输出行的二次 `_truncate_search_content` 截断，rg 已通过 `--max-columns` 在输出阶段限制单行字节。

### 子进程/线程清理优化

- `_run_rg_pipeline` 的 finally 清理逻辑中，先显式关闭最后一个子进程的 stdout 管道，确保后台读取线程立即收到 EOF 退出。
- 线程 join 超时从 200ms 延长至 3s，降低线程残留概率。
- 关闭流时增加 `OSError` 异常捕获，避免双重关闭导致异常。

### 文件编码检测缓存

- `_detect_file_encoding` 优先从已有的 `.lineidx` 行索引文件中读取缓存的编码，避免重复调用 `charset_normalizer` 实时探测。
- 索引不存在或无效时回退到原有的实时探测逻辑。

## 注意事项

- 页缓存释放后，下次搜索同一工单日志时需重新从磁盘读取，对搜索速度有轻微影响（毫秒级），但换来内存稳定性。
- `_match_keywords` 方法保留，在 Python 降级搜索路径中仍承担搜索匹配职责。
- 以上优化均不影响前端行为，无需前端配合。