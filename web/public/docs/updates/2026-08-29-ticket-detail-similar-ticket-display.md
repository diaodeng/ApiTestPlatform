# 工单详情页相似工单展示调整

- 变更日期：2026-08-29
- 变更范围：工单管理 → 工单详情弹窗（概览 tab、协同/AI tab）。

## 变更内容

- 概览 tab 的相似工单卡片由默认展示 3 条调整为展示 5 条，与接口默认返回数量（`limit=5`）保持一致。
- 协同/AI tab 移除右侧"相似工单"卡片；相似工单候选的查看和"归入同一问题"操作统一收敛到概览 tab。

## 使用说明

- 相似工单的 **系统详情**、**飞书详情** 和 **归入同一问题** 操作入口不变，仍在概览 tab 的相似工单卡片中。
- 发起 AI 分析不受影响：AI 分析上下文中的相似工单由后端在分析时自动检索（每次取 5 条），不依赖详情页展示的候选列表。

## 技术说明

- 前端组件：`web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`（相似工单展示条数调整为 5）、`web/src/views/ticket/components/detail-tabs/TicketDetailCollabTab.vue`（移除相似工单卡片及归因、外部链接跳转等仅服务于该卡片的代码）、`web/src/views/ticket/components/TicketDetailWithList.vue`（不再向协同 tab 传入相似工单数据）。
- 未修改后端接口和 AI 分析逻辑。

## 注意事项

- 协同/AI tab 中如需将当前工单与相似工单归入同一问题，请前往概览 tab 操作。
