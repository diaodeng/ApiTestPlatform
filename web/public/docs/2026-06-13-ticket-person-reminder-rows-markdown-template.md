# 按人催办明细行模板可配置

## 背景

`TicketSyncNotifyService.run_person_overdue_reminder` 里的 `rows_markdown` 之前是后端固定样式拼接，前端只能在整段 `messageTemplate` 中插入 `${rows_markdown}`，无法单独控制每条明细的展示格式。

## 变更

新增 `personReminder.rowsMarkdownTemplate` 配置，用于单独控制每条超时明细的 Markdown 生成方式。

### 默认值

未配置时仍保持原有展示逻辑，默认生成类似下面的内容：

`1. [2026-06-13 10:00:00]（工单号: TICKET-001） [详情](https://...)`

### 可用变量

- `${index}` / `${row_index}`: 明细序号
- `${created_at}` / `${createdAt}`: 创建时间
- `${ticket_no}` / `${ticketNo}`: 工单号
- `${detail_url}` / `${detailUrl}`: 详情链接
- `${detail_link}` / `${detailLink}`: 已包装好的详情链接片段

### 示例

```text
- 第${index}条 | ${created_at} | ${ticket_no}${detail_link}
```

## 影响范围

- 后端：`server/modules/ticket/service/ticket_sync_notify_service.py`
- 配置归一化：`server/modules/ticket/service/ticket_sync_service.py`
- 前端配置页：`web/src/views/ticket/syncAutomation/index.vue`

## 兼容性

- 旧配置不受影响，`rowsMarkdownTemplate` 为空时自动回退到默认样式。
- `messageTemplate` 仍然只负责整段消息模板，`rows_markdown` 负责承载已渲染好的明细内容。
