# 2026-06-11 工单群消息优先级分流修复（外部推单）

## 背景

外部系统推单后，群消息虽然会发送，但常出现只落到 `groupPush.pushIds/appChatIds` 默认目标，不按 `priorityRoutes` 分路发送的问题。

## 根因

1. 外部同步接口只强制接收并写入了 `internalPriority/internal_priority`，未显式写入 `customerPriority/customer_priority`。
1. `TicketExternalSyncUpsertModel` 继承基础模型后，`customer_priority` 会带默认值 `P3`。
1. 群推送路由优先级解析逻辑按 `customer_priority -> internal_priority` 顺序取值，导致很多外部工单被解析成 `P3`，无法按真实优先级分流。

## 改动

1. 外部同步入参归一化时补充 `customer_priority` 映射：
   - 优先读 `customerPriority/customer_priority`；
   - 未提供时回退 `ticketPriority/ticket_priority`；
   - 再回退 `internalPriority/internal_priority`。
1. 群推送优先级归一化增强：
   - 兼容 `P1/P2/P3/P4`、`1/2/3/4`、`P 1`、`P1-紧急` 等表达。
   - 增加常见中英文优先级关键字映射（如 `urgent/high/medium/low`、`紧急/高/中/低`）。
1. 路由 chat_id 字段兼容增强：
   - `priorityRoutes` 子项同时支持 `chatIds` 与 `appChatIds`。
1. 路由未命中日志补齐：
   - 当配置了 `priorityRoutes` 但当前工单优先级未命中时，记录 `warning`，包含工单号、解析优先级、路由优先级列表与最终回退目标。

## 影响范围

1. `POST /ticket/sync/external` 外部推单字段归一化。
1. 外部推单后自动群推送（`external_sync` 场景）分路行为。
1. 手动/远端拉取场景的路由解析兼容性（仅增强，不改变原有开关语义）。

## 验证建议

1. 配置 `priorityRoutes`（至少配置 P1/P2/P3-P4 三组不同群）。
1. 依次推送不同优先级工单（如 `internalPriority=P1/P2/P3`）。
1. 确认消息落到对应路由目标，而非总是默认群。
1. 推送一个无法映射的优先级（如 `internalPriority=UNKNOWN`），确认日志出现“路由未命中，回退默认目标”的告警。
