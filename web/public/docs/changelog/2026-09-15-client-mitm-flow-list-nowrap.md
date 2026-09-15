# 2026-09-15 - 桌面客户端 mitmproxy 流量列表单行显示

## 变更内容

桌面客户端（client_new）「mitmproxy」页流量列表此前受全局表格样式 `word-break: break-all` 影响，URL / Path 较长时单元格会折行，导致行高不齐、列表难读。本次调整：

- 流量表所有列强制单行显示（`white-space: nowrap`），不再折行。
- 时间、方法、状态、大小、耗时、断点列按典型内容定宽完整展示，Host 列占固定比例宽度。
- Path 列占满剩余空间，超长时显示省略号（`…`），并为单元格补充 `title` 属性，悬停可查看完整路径。
- 列宽支持手动拖拽调整：除 Path 列外，表头右缘有拖拽手柄，按住左右拖动调整列宽（Path 列自动反向伸缩），双击手柄恢复默认；调整结果存入 localStorage，重启客户端后仍生效。

## 变更文件

- `client_new/ui_web/static/js/pages/mitm.js`：流量表新增 `mitm-flow-table` 类与 `colgroup` 列宽定义；Path 列单元格新增 `flow-path` 类与 `title` 提示；新增 `setupColumnResize` 列宽拖拽逻辑（含持久化与双击复位）。
- `client_new/ui_web/static/css/app.css`：新增 mitmproxy 流量表专用样式（固定布局 + 全列单行 + Path 列省略 + 拖拽手柄样式）。
- `web/public/docs/client/mitm-proxy.md`：新增「流量列表展示」说明。

## 影响范围

仅影响 mitmproxy 页流量列表的展示样式，不涉及任何业务逻辑、数据与接口变更。
