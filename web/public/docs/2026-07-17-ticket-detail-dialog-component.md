# 工单详情弹窗自闭环组件说明

## 背景

工单列表页 `web/src/views/ticket/index.vue` 原本同时承载列表筛选、增删改、导入、指派、状态流转、详情、AI、日志查看等多个弹窗。详情页已先迁移过部分模板到 `TicketDetailWithList.vue`，但仍通过 `ticketDetailContext` 依赖父页大量状态和函数，不利于继续拆分和维护。

## 本次调整

1. `web/src/views/ticket/components/TicketDetailWithList.vue` 改为自闭环详情组件，只接收 `open` 和 `ticketId`，内部自行加载工单详情、评论、时间线、日志拉取记录、AI 任务和选项数据。
2. AI 分析、AI 任务历史、任务原文、仓库映射、商家映射、新建问题绑定和日志查看器弹窗已迁入详情组件内部。
3. 详情组件恢复完整详情内容，保留顶部基础信息、描述/AI 翻译、相似问题提示和下方详情 tabs，避免只展示顶部表格。
4. 下方 tabs 已拆成独立子组件：

- `components/detail-tabs/TicketDetailOverviewTab.vue`：最新 AI 结论和相似工单。
- `components/detail-tabs/TicketDetailLogPullTab.vue`：日志拉取记录、提交拉取任务、日志查看入口。
- `components/detail-tabs/TicketDetailCollabTab.vue`：协同消息、AI 分析入口、快照和知识库生成。
- `components/detail-tabs/TicketDetailCommentsTab.vue`：评论提交和评论列表。
- `components/detail-tabs/TicketDetailHistoryTab.vue`：时间线、排查事件和 RCA。

5. `web/src/views/ticket/index.vue` 只保留：

```vue
<TicketDetailWithList
  v-model:open="detailOpen"
  :ticket-id="currentTicketId"
  @changed="getList"
  @closed="handleDetailClosed"
/>
```

6. 父页删除 `ticketDetailContext`、详情数据、评论/消息/RCA/AI/日志查看器状态和对应处理函数，只负责设置当前工单 ID、打开详情和在详情变更后刷新列表。
7. 日志拉取表单默认值和清洗逻辑下沉到 `web/src/views/ticket/logPull.shared.js`，供父页新增/编辑表单和详情组件共同复用；父页不再为了默认值初始化 `useLogViewer`。
8. 日志拉取 tab 拆出后，`TicketDetailLogPullTab.vue` 需要自行注册 `LogPullConfigFields` 和 `LogPullNotifyConfigFields`；父组件 import 不会透传到子组件模板。

## 组件边界

1. 详情组件输入：`ticketId`、`open`。
2. 详情组件输出：`update:open`、`changed`、`closed`。
3. 详情组件内部闭环：详情接口请求、描述翻译、评论、协同消息、事件、RCA、快照、知识提炼、AI 分析任务、仓库映射、商家映射、问题绑定/解绑、日志拉取和日志查看。
4. 详情 tabs 子组件只服务于详情组件内部展示和交互分组，不要求工单列表页传入详情上下文。
5. 父页保留能力：列表查询、导入、新增/编辑、指派、状态流转、版本批量维护和版本统计。

## 验证

已执行：

```bash
cd web
npm run build:prod
```

构建通过；仅保留项目既有 Vite 警告（`config.js` 非 module script、`utils/tools.js` eval 提示、chunk 体积提示）。构建后已清理 `web/dist` 产物。
