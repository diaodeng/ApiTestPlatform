# 2026-09-02 问题实例绑定工单操作列新增外部地址按钮

## 变更内容

问题实例详情的"绑定工单"列表中，每行操作列在"打开工单"和"解绑"之间新增 **外部地址** 按钮，点击在新标签页打开该工单的外部系统详情链接（如 ITSM 工单原始页面）。

- 仅当工单存在外部链接时显示该按钮；无链接的工单不显示（按钮不会处于置灰占位状态）。
- 链接解析与工单列表页"跳转"、工单详情页"外部链接"使用同一套多级兜底逻辑：工单链接字段（`ticketUrl`，含后端同步摘要兜底）→ 同步摘要（`syncSummary`）→ 扩展字段 `extraData.externalSync.source`。
- 操作列宽度从 200px 调整为 260px 以容纳三个按钮。

## 改动文件

### 后端
- `server/modules/ticket/service/issue/ticket_issue_service.py`：`get_issue_detail_services` 查询绑定工单后，逐行调用 `TicketService._decorate_ticket_item` 补充同步摘要装饰——此前该列表未做装饰，`ticketUrl` 为空的工单无法像工单列表一样按 `extraData` 同步摘要兜底出链接。

### 前端
- `web/src/views/ticket/constants.js`：新增共享函数 `resolveTicketDetailUrl`（从 `useTicketList.js` 下沉），供工单列表、问题实例页等多处复用。
- `web/src/views/ticket/hooks/useTicketList.js`：删除本地重复实现，改为从 `constants.js` 导入并原样返回（对外契约不变）。
- `web/src/views/ticket/issue/index.vue`：绑定工单操作列新增"外部地址"按钮（`v-if` 有链接才显示）及 `openExternalTicketLink` 处理函数。

## 相关说明
- [问题实例管理](../ticket_issue.md)
