# 日志拉取下载来源修复

## 背景

日志拉取记录有两类文件来源：本服务保存的归档文件（本地或 FTP）和外部平台返回的原始压缩包地址。此前日志拉取管理页和工单详情页下载语义不够清晰：管理页需要优先下载本服务归档，缺失时再回退原始地址；工单详情页则需要将“归档地址”和“原始压缩包”拆成两个明确入口。

## 变更

1. 后端下载接口 `/ticket/log-pulls/{record_id}/download` 新增 `source` 查询参数：
   - `auto`：默认策略，优先本服务归档文件，本服务文件不存在或未下载时回退原始下载路径。
   - `service`：只下载本服务保存的归档文件。
   - `original`：只下载外部平台原始压缩包地址。

2. 日志拉取管理页点击“下载日志”显式使用 `source=auto`，满足优先本服务归档、缺失再回退原始路径。

3. 工单详情页日志拉取列表调整：
   - 增加商家、门店、POSID 三列，便于同一工单下区分不同 POS 的日志拉取记录。
   - 点击“归档地址”走 `source=service`，从本服务下载本地/FTP 归档文件。
   - 点击“原始压缩包”走 `source=original`，从原始下载路径下载。

## 验证

- 已执行 `uv run python -m py_compile modules\ticket\controller\ticket_controller.py modules\ticket\service\ticket_log_pull_service.py`。
- 已执行 `uv run ruff check modules\ticket\controller\ticket_controller.py modules\ticket\service\ticket_log_pull_service.py`。
- 已执行 `cd web && npm run build:prod`，构建通过；仅保留既有 `config.js`、`eval` 和 chunk 体积提示。
