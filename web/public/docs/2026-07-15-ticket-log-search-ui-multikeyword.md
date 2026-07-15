# 2026-07-15 工单日志搜索面板与多关键字高亮

## 结论

- 工单日志搜索支持多个关键字，搜索模式可选“任一”或“全部”，后端仍保留旧 `keyword` 入参兼容。
- 日志查看器的搜索结果区和上下文区在另一侧最小化或无上下文时会自动填满剩余空间。
- 高亮从“选中文案自动触发”改为独立输入框维护，避免复制日志内容时因状态刷新导致浏览器选区丢失。
- 工单详情和日志拉取记录页的日志拉取表格取消固定操作列，并常显横向滚动条，改善拖动横向滚动条时卡顿、不顺畅的问题。

## 搜索契约

`/ticket/logs/search` 请求体新增字段：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `keywords` | `[]` | 多关键字列表，最多 10 个，每个最多 200 字符 |
| `searchMode` | `any` | `any` 表示任一关键字命中，`all` 表示同一行必须包含全部关键字 |
| `keyword` | `null` | 兼容旧单关键字入参，会合并到 `keywords` |

响应命中项新增 `matchedKeywords`，用于标识当前行实际命中的关键字。

## 实现要点

1. 后端 `LogService.search_keywords(...)` 作为多关键字入口，单关键字继续复用原 `search(...)`。
2. ASCII 多关键字 `any` 模式优先使用 `rg --fixed-strings -e` 按文件搜索；`all` 模式、中文关键字或无 `rg` 环境时使用 Python 行扫描。
3. 多关键字搜索继续受 `maxSearchSeconds/maxSearchFileCount/maxPythonSearchBytes` 保护，返回结果仍由 `limit` 截断。
4. 前端搜索输入改为可创建的多选框；高亮输入独立维护，支持多个字符串同时高亮并使用不同背景色区分。
5. 日志上下文 `<pre>` 不再绑定鼠标选中事件，复制文本时不会触发高亮状态更新。
6. 日志拉取记录表格使用 `scrollbar-always-on`，并移除右侧固定操作列，避免横向滚动条与固定列布局互相影响。

## 影响范围

- 后端接口：`/ticket/logs/search`。
- 前端页面：工单详情日志查看器、工单详情日志拉取列表、日志拉取记录管理页。
- 兼容性：旧前端或外部调用仍可只提交 `keyword`；新前端会提交 `keywords/searchMode`。

## 验证

- `cd server; uv run python -m py_compile modules/ticket/service/log_pull/ticket_log_service.py modules/ticket/controller/ticket_log_pull_controller.py modules/ticket/entity/vo/ticket_log_pull_vo.py`
- `cd server; uv run ruff check modules/ticket/service/log_pull/ticket_log_service.py modules/ticket/controller/ticket_log_pull_controller.py modules/ticket/entity/vo/ticket_log_pull_vo.py`
- 后端 smoke：`LogService.search_keywords(...)` 覆盖 `any/all` 两种模式。
- `cd web; npm run build:prod`
