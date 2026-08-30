# 工单状态展示为状态名称

- 变更日期：2026-08-29
- 变更范围：问题实例管理 → 问题实例详情绑定工单列表；工单管理 → 独立工单详情页。

## 变更内容

- 问题实例详情页的“绑定工单”列表中，状态列由直接显示状态编码（如 `processing`、`resolved`）改为显示状态名称（如“处理中”“已解决”），并以标签形式展示颜色，与工单列表页保持一致。
- 独立工单详情页（`/ticket/detail/{ticketId}`）顶部标题栏的状态由直接显示状态编码改为以标签形式显示状态名称，颜色与工单列表页一致。
- 两处均支持自定义工作流状态节点：加载工作流配置后按状态编码匹配名称；匹配不到时回退默认枚举，仍匹配不到则原样显示状态编码，不会显示空白。

## 技术说明

- 前端复用既有 `web/src/views/ticket/hooks/useWorkflow.js` 的 `ticketStatusOptions`（合并自定义工作流状态节点与默认枚举），保证与工单列表页的状态名称来源一致。
- `web/src/views/ticket/issue/index.vue`：新增 `formatTicketStatus` / `getTicketStatusTagType`，绑定工单状态列改用标签展示；页面挂载时调用 `loadWorkflowConfig()`。
- `web/src/views/ticket/components/TicketDetailView.vue`：接入 `useWorkflow`，顶部状态改用标签 + `formatTicketStatus` 展示；`loadDetail` 加载完成后同步 `currentTicketStatus`。
- 未修改任何后端接口：后端返回的状态字段仍为编码，名称转换在前端完成。

## 注意事项

- 若工作流配置接口加载失败，将回退为默认状态枚举名称；未知状态编码会原样展示。
- 问题实例列表、问题实例详情顶部等处的问题实例状态（open/processing 等）此前已显示名称，本次未改动。
