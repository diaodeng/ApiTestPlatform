# 多维表格主动拉取优先级与人员字段兜底修复

## 变更日期

- 2026-06-24

## 结论

- 修复飞书多维表格主动拉取中“内部优先级/对方优先级”取值不一致的问题：当内部优先级来源字段为空、对方优先级有值时，主动拉取会使用对方优先级兜底内部优先级。
- 修复主动拉取中部分“当前处理人”和“内部负责人”为空的问题：主动拉取字段映射现在兼容 `ticketAssigneeName/assigneeName` 等当前处理人别名，并把人员值同步写入顶层模型和 `extraData.external_field_mapping`。
- 本次只修改主动拉取记录转换层，不改 `POST /ticket/sync/external` 外部推送入口和多维表格邮箱补齐逻辑。

## 问题位置

- `server/modules/ticket/service/ticket_sync_service.py`
  - `_normalize_bitable_pull_target_field()`
  - `_build_bitable_pull_sync_object()`

## 根因

- 外部推送会先经过 `server/modules/ticket/controller/ticket_controller.py` 的 `_normalize_ticket_external_sync_payload()`，该层会做人员字段别名、外部字段快照等归一化。
- 多维表格主动拉取为了复用外部同步主链路，直接在 `_build_bitable_pull_sync_object()` 中构造 `TicketExternalSyncUpsertModel`，不会经过外部推送 controller 的归一化层。
- 因此主动拉取映射得到的部分外部字段只停留在原始 payload 中，未同步到 Pydantic 模型顶层字段；落库时 `_build_upsert_payload()` 又优先读取顶层 `customer_priority/internal_priority/current_assignee_name/internal_owner_name`，导致优先级兜底和人员展示缺失。

## 关键实现

- `_normalize_bitable_pull_target_field()` 新增当前处理人别名：
  - `ticketAssigneeName/ticket_assignee_name/assigneeName/assignee_name` -> `ticketAssignee`
  - `ticketAssigneeEmail/ticket_assignee_email/assigneeEmail/assignee_email` -> `ticketAssigneeEmail`
- `_build_bitable_pull_sync_object()` 在主动拉取内部补齐兼容语义：
  - `internalPriority` 为空且 `customerPriority` 有值时，`internalPriority = customerPriority`
  - `customerPriority` 为空且 `internalPriority` 有值时，`customerPriority = internalPriority`
  - `currentAssigneeName/currentAssigneeEmail` 与 `ticketAssignee/ticketAssigneeEmail` 互相兜底
  - `customerPriority/internalPriority/currentAssigneeName/internalOwnerName` 等字段同步保留在顶层模型与 `extraData.external_field_mapping`

## 验证

- `uv run ruff check modules/ticket/service/ticket_sync_service.py tests/test_ticket_sync_mapping_boundary.py`
- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`

## 风险

- 本次没有修改外部推送 controller 和多维邮箱补齐函数，外部推送数据逻辑不受影响。
- 主动拉取仍不会凭空生成人员或优先级；只有配置映射到的多维字段存在值时才会兜底。
