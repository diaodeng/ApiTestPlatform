# 2026-06-19 工单日志统一查看服务

## 结论
- 新增 `LogService` 作为工单日志查看、搜索、上下文和异常摘要的统一入口，供 Web、AI Agent 和后续 CLI 复用。
- Web 工单列表新增“日志”入口，工单详情日志拉取弹窗内新增关键词搜索、时间搜索、异常提取和上下文翻页。

## 后端变更
- 新增 `server/modules/ticket/service/ticket_log_service.py`。
- 目录结构落到 `data/logs/ticket_{ticket_id}`：
  - `source/log.zip` 保存归档副本。
  - `extract/` 保存递归解压后的日志文件。
  - `meta.json` 保存准备元数据。
- 新增接口：
  - `POST /ticket/logs/prepare`
  - `GET /ticket/logs/files`
  - `POST /ticket/logs/search`
  - `GET /ticket/logs/context`
  - `POST /ticket/logs/search_time`
  - `POST /ticket/logs/errors`
- 搜索读取模式由环境变量 `TICKET_LOG_SEARCH_MODE` 控制，取值 `auto/native/python`：
  - 默认 `auto`，优先查找 `rg`、`rg.exe`、`ripgrep`、`ripgrep.exe`。
  - 找不到原生工具或原生工具执行失败时，会记录日志并降级为 Python 逐文件搜索。
  - `python` 强制使用 Python 读取，适合没有 ripgrep 的环境。
- 上下文读取模式由环境变量 `TICKET_LOG_CONTEXT_MODE` 控制，取值 `auto/native/python`：
  - 默认 `auto` 使用 Python 行偏移索引读取，适合按行号精确取前后文。
  - `native` 会尝试用系统命令读取当前文件行段：Windows 使用 PowerShell，Linux/macOS 使用 `sed`；失败后降级为 Python 行偏移索引。
  - `python` 强制使用 Python 行偏移索引。
- 上下文读取使用 `.lineidx` 行偏移索引：
  - 首次查看某个日志文件时扫描一次生成“行号 -> 字节偏移”索引。
  - 后续按前端传入的中心行号和前后行数直接 `seek` 读取目标行段，不再为每次上下文查看扫描整份日志。
  - 索引会校验源文件大小和修改时间，文件变化后自动重建。
- 上下文支持日志轮转文件边界补齐：
  - 同一目录、同一基名的 `app.log`、`app.log.1`、`app.log.2` 会按轮转组处理。
  - 数字越大越旧，数字越小越靠近当前；向前补上下文时读取更旧文件尾部，向后补上下文时读取更新文件头部。
  - 响应会返回 `prevFile/prevLine`、`nextFile/nextLine`，供前端跨文件翻页。
- 接口内部通过 `run_in_threadpool` 调用同步文件和压缩包处理逻辑，避免阻塞 FastAPI 事件循环。

## 解压与文本识别
- 标准库支持 `.zip`、`.tar`、`.tar.gz`、`.tgz`、`.gz`、`.bz2`、`.xz`。
- `.rar` 和 `.7z` 通过系统 `7z` 命令解压，机器未安装 7z 时会明确返回失败原因。
- 递归解压最多 20 轮，解压后删除中间压缩包，直到目录中没有受支持的压缩文件。
- 日志文件识别不只看 `.log`，还支持 `.txt`、`.out`，并通过 `charset-normalizer` 探测无扩展名文本文件。

## 前端变更
- `web/src/api/ticket/ticket.js` 新增日志查看 API 封装。
- `web/src/views/ticket/index.vue`：
  - 工单列表操作列增加“日志”按钮，会先调用 prepare，再打开日志查看弹窗。
  - 原日志内容弹窗保留入库内容/原始文档能力。
  - 新增关键词搜索、时间搜索、异常提取、命中列表和上下文查看。
  - 上下文支持上一段/下一段翻页，行数由“上下文”输入框控制。

## 注意事项
- 当前实现复用最新一条日志拉取记录的归档文件或原始下载地址，不新增数据库表。
- 推荐服务端安装 `rg`，搜索会更快；未安装时会自动降级为 Python 搜索。
- 按行号读取上下文时，Python 行偏移索引更适合当前需求；原生命令方式每次通常仍需要从文件头扫描到目标行，主要作为可配置兼容方案保留。
- 处理 `.rar`、`.7z` 需要安装 `7z`。
