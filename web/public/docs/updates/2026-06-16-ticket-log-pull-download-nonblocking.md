# 日志拉取下载非阻塞修复

## 背景

日志拉取列表中的“归档地址”“原始压缩包”“重新下载”入口在大文件场景下会触发后端同步下载、FTP 读取或数据库查询。由于这些入口所在路由是 `async def`，如果直接调用同步 SQLAlchemy、`requests` 或文件/FTP 操作，会占用 FastAPI 事件循环，导致服务在下载期间无法及时响应其他请求。

## 变更

1. 工单详情页“原始压缩包”不再请求后端 `/ticket/log-pulls/{id}/download?source=original`，改为直接打开记录中的 `commandResultUrl`，由浏览器使用原始地址下载。
2. 工单详情页“归档地址”如果是 HTTP 地址会直接由浏览器打开；本地/FTP 归档仍走后端下载接口，但后端文件解析逻辑放入线程池，避免阻塞事件循环。
3. 日志拉取管理页“下载”在没有本服务归档且存在原始地址时直接打开原始地址；存在本服务归档时保留鉴权接口下载。
4. 工单外部推送、内网 pending 拉取、ack、日志内容读取、日志列表、日志拉取提交、重新拉取、重新下载、重新截取和删除等高风险同步服务调用显式使用 `run_in_threadpool`。
5. 取舍原则：`def` 路由可以让 FastAPI 自动线程池调度；但当前接口需要保留 `async def` 以兼容请求体异步读取和后台任务编排，因此在 `async def` 内对同步数据库/网络/文件调用显式使用 `run_in_threadpool` 更明确、更可控。

## 影响

- 原始压缩包下载不再消耗本服务带宽和 worker 时间。
- `重新下载`仍保持“服务端重新从原始地址拉回并恢复归档”的业务语义，但不会阻塞事件循环。
- 外部推送与内网拉取主接口仍是同步完成入库后返回，慢 SQL 或批量数据处理会占用线程池线程，但不会直接卡住事件循环。

## 验证

- 已执行 `uv run python -m py_compile modules\ticket\controller\ticket_controller.py`。
- 已执行 `uv run ruff check modules\ticket\controller\ticket_controller.py`。
- 已执行 `cd web && npm run build:prod`，构建通过；仅保留既有 `config.js`、`eval` 和 chunk 体积提示。
