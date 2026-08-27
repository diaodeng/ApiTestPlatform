# 2026-08-27 工单导出功能

## 新增功能

### 工单列表导出
- 工单列表页新增 **导出** 按钮，支持导出工单为 Excel 文件。
- 支持两种导出模式：
  - **选中导出**：表格勾选工单后，导出选中的工单。
  - **筛选导出**：未勾选时，按当前筛选条件导出全部匹配工单。
  - 自然语言搜索场景：未勾选时按当前页面可见结果导出。
- 导出列可手动选择，默认全选，列名与 Web 页面一致。
- 新增权限：`ticket:ticket:export`。

### 问题实例关联工单导出
- 问题实例管理页表格新增 **复选框** 列。
- 新增 **导出工单** 按钮，导出选中问题实例下绑定的工单。
- 导出列包含并默认勾选"问题编号"和"问题名"（必选列）。
- 导出列可手动选择，默认全选。
- 新增权限：`ticket:issue:export`。

## 技术实现

### 后端
- 新增 `server/modules/ticket/entity/vo/ticket_export_vo.py` — 导出请求 Pydantic 模型。
- 新增 `server/modules/ticket/util/ticket_excel_export_util.py` — Excel 生成工具，支持流式文件写入和最大列宽限制。
- 新增 `server/modules/ticket/service/export/ticket_export_service.py` — 导出服务，管理列定义、数据查询、格式化。
- 新增 `POST /ticket/export` 接口 — 工单列表导出。
- 新增 `POST /ticket/issues/export-tickets` 接口 — 问题实例关联工单导出。
- 新增权限 `ticket:ticket:export` 和 `ticket:issue:export`。

### 前端
- `web/src/api/ticket/ticket.js` — 新增 `exportTickets` 和 `exportIssueTickets` API 方法。
- `web/src/views/ticket/index.vue` — 新增导出按钮、列选择弹窗和导出逻辑。
- `web/src/views/ticket/issue/index.vue` — 新增表格复选框、导出工单按钮、列选择弹窗和导出逻辑。

### 导出限制
- 单次导出上限：10000 行。
- Excel 文件格式：.xlsx，表头加粗、浅色背景、冻结首行。
- 状态字段自动映射为中文（如 `pending` → `待受理`）。

## 相关文档
- [工单列表导出使用说明](./ticket/ticket-list-export.md)
- [问题实例关联工单导出使用说明](./ticket/issue-ticket-export.md)

## 2026-08-27 导出异常修复

- 修复 DAO 分页结果被错误转换为字段元组，导致导出时报 `tuple` 没有 `get` 方法的问题。
- 修复前端 Blob 响应仍按 Axios 完整响应读取 `headers.content-disposition` 导致下载失败的问题。
- 未选择工单时，导出请求会携带当前列表筛选条件；单次导出仍限制最多 10000 行。
