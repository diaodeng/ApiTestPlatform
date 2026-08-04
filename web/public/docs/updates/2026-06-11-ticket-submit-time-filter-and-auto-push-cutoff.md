# 2026-06-11 工单提交时间筛选与自动群推送起始时间

## 背景

自动群推送需要增加“按提交时间启用”的能力，同时工单列表需要展示并筛选“工单提交时间”。

业务规则：

1. 提交时间优先取外部推单 `createTime`。
1. 当外部 `createTime` 缺失，或工单为手动创建时，回退本地 `ticket.create_time`。
1. 自动群推送仅在“未推送过且提交时间晚于配置时间”时发送。

## 改动

1. 新增自动群推送起始时间配置：
   - 配置项：`groupPush.autoSendAfterTime`。
   - 页面位置：工单同步自动化配置 -> 工单群消息推送 -> 自动推送起始时间。
   - 自动推送执行前会比较工单提交时间与该配置；提交时间 `<=` 配置值时跳过发送。
1. 工单列表新增“提交时间”字段：
   - 返回字段：`submitTime`（外部 `createTime` 优先，本地创建时间回退）。
   - 同时保留兼容字段 `externalCreateTime` 便于前端回退展示。
1. 工单列表新增“提交时间”筛选：
   - 查询参数：`submitBeginTime`、`submitEndTime`。
   - 后端过滤表达式按“外部提交时间优先，本地创建时间回退”执行。
1. 页面改动：
   - 工单列表页新增“提交时间”筛选控件（时间范围）。
   - 工单列表表格新增“工单提交时间”列。

## 影响范围

1. 后端：
   - `TicketSyncService` 自动群推送拦截逻辑。
   - `TicketDao.get_ticket_list` 提交时间过滤逻辑。
   - `TicketService` 列表项装饰字段（`submitTime`）。
   - `TicketQueryModel` 查询参数扩展。
1. 前端：
   - `ticket/syncAutomation` 配置页新增字段。
   - `ticket/index` 列表页新增展示与筛选。
