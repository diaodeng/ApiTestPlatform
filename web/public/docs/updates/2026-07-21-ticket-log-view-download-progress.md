# 2026-07-21 查看日志远程下载进度

## 结论

工单详情的日志拉取列表和日志拉取管理列表在查看日志时，若后端需要从 HTTP 或 FTP 重新下载归档文件，会把当前行的“查看日志”入口替换为不可点击的圆形进度条。进度依据下载字节数和文件总大小实时计算；本地归档或已准备缓存不触发进度条。

## 接口契约

`POST /ticket/logs/prepare` 保持原请求与响应不变。准备任务开始后，前端每 400ms 查询：

`GET /ticket/logs/prepare-progress?ticket_id={ticketId}&record_id={recordId}`

返回字段：

| 字段 | 说明 |
| --- | --- |
| `stage` | `idle`、`preparing`、`downloading`、`completed` 或 `failed` |
| `downloading` | 是否正在远程下载，前端仅在此值为 `true` 时替换按钮 |
| `percentage` | 已下载百分比；源站未返回文件大小时为 `0`，完成后由准备请求结束 |
| `downloaded` / `total` | 已下载和总字节数，用于排查进度异常 |
| `source` | 下载来源：`http` 或 `ftp` |
| `message` | 当前阶段说明 |

## 行为规则

1. 详情页查看日志始终先准备可搜索目录，若远程归档不存在于本地则下载并解压。
2. 管理页查看“入库内容”不下载；选择“原始文档”实时查看时先准备源包，以相同进度机制展示下载状态。
3. 已准备的 `data/logs/ticket_{ticketId}/record_{recordId}/source` 源包会被实时查看复用，避免管理页再次下载同一归档。
4. 进度状态通过应用级异步 Redis（`app.state.redis`）共享，TTL 30 分钟；多实例部署时轮询请求可命中任意实例。若缓存后端配置为 `memory`，则退化为单进程内存存储。

## 验证

- 后端：`uv run ruff check ...` 与 `uv run python -m compileall ...`。
- 前端：`npm run build:prod`。
