# 2026-09-02 工单导出新增 URL 列

## 变更内容

问题实例管理和工单列表两处导出功能的导出列新增 **URL** 选项，用于导出工单详情链接（`ticket_url`）。

- 工单列表导出（`导出工单` 对话框）：导出列勾选项新增 URL，默认全选时包含该列。
- 问题实例关联工单导出（`导出问题实例关联工单` 对话框）：导出列勾选项新增 URL，默认全选时包含该列。
- URL 列仅用于导出，工单列表的表格"列设置"中不提供该列（不影响页面展示配置）。
- 取值优先级：工单详情链接字段（`ticket_url`）→ 同步摘要中的工单链接 / 来源记录链接（`extraData` 兜底，与工单详情页展示的链接一致）。无链接时单元格为空。

## 改动文件

### 后端
- `server/modules/ticket/service/export/ticket_export_service.py`：
  - `TICKET_EXPORT_COLUMNS`（工单列表导出列定义）在"标题"后新增 `ExportColumn(key="ticketUrl", label="URL")`。
  - `ISSUE_TICKET_EXPORT_COLUMNS`（问题实例关联工单导出列定义）同样新增 URL 列。
  - `_format_ticket_field()` 新增 `ticketUrl` 分支：取装饰后的 camelCase `ticketUrl`（含 `_decorate_ticket_item` 的同步摘要兜底），snake_case `ticket_url` 兜底，空值输出空字符串。

### 前端
- `web/src/views/ticket/hooks/useTicketList.js`：新增 `ticketExportColumnOptions` 导出列配置（复制显示列后在其间插入 URL 项），与表格显示列配置 `ticketColumnOptions` 拆分，避免 URL 混入表格"列设置"。
- `web/src/views/ticket/index.vue`：导出列对话框复选框改用 `ticketExportColumnOptions`，重置默认改为按导出列配置全选。
- `web/src/views/ticket/issue/index.vue`：问题实例导出工单列配置 `issueTicketExportColumnOptions` 新增 `{ key: 'ticketUrl', label: 'URL' }`（标题之后）。

### 测试
- `server/tests/test_ticket_export_service.py` 新增 2 个用例：
  - 两处导出列定义均包含 `ticketUrl`/`URL` 列。
  - `ticketUrl` 格式化：camelCase 取值、snake_case 兜底、空值输出空字符串。

## 相关说明
- [工单列表导出](../ticket/ticket-list-export.md)
- [问题实例关联工单导出](../ticket/issue-ticket-export.md)
