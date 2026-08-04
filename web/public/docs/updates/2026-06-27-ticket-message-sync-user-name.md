# 2026-06-27 工单排查过程消息同步用户名解析

## 结论

飞书话题评论同步到当前系统和多维表格排查过程时，发送人不再直接记录飞书 `open_id/union_id`。服务会使用消息事件中的 `sender.open_id` 调用飞书通讯录用户详情接口，优先写入飞书用户名。

2026-06-28 追加：飞书消息正文中的 `@_user_1` 这类占位符会按 `message.mentions[].key` 映射为 `@用户名` 后保存到工单系统，同时把 `openId/userId/unionId` 和正文片段保存到评论 `attachments.content_segments`。后续写回多维表格或飞书群时，会用片段恢复为真实 @ 人员样式。

## 变更范围

1. `TicketMessageSyncService.handle_feishu_message_event()` 在确认消息需要写入工单评论或多维表格时，先解析发送人展示名。
2. `TicketSyncNotifyService.query_feishu_user_by_open_id()` 新增按 `open_id` 查询飞书用户详情能力。
3. 用户名解析优先使用 `ticket.sync.automation.feishuAuth` 统一凭证；缺失时才从群推送或多维运行时配置兜底读取飞书应用凭证。
4. 工单评论 `user_name` 和追加到多维表格排查过程 `{user}` 使用同一个解析结果，避免系统内和多维表格显示不一致。
5. 飞书消息入站含 `mentions` 时，系统评论 `content` 保存可读文本，`attachments.mentions/content_segments` 保存人员 ID 和片段。
6. 写回多维表格排查过程时，若评论正文含 @ 人员片段，会写入含 `mention_user_id` 的富文本片段数组。
7. 多维表格主动拉取 `stepReason` 时，若 Text 字段返回富文本片段数组，会把 `mention_user_id` 片段归一为 `@用户名`，并把片段带入同步评论附件；再同步到飞书群时可恢复 `<at user_id="..."></at>`。

## 样例查询

工单 `INC00001673345` 本地关联多维表格记录 `recvnBIIgiaV9M`，排查过程配置字段为 `跟進過程沟通和结论...格式`，字段元数据 `ui_type=Text`、`type=1`。本次查询该多维记录时，飞书接口未返回该排查过程字段值（通常表示当前单元格为空或未在返回字段中出现）；本地历史值为 `20260626 熊杰：@Ken Pong门店3042下的3号机台没有做日结`。

## 兜底规则

1. 未拿到 `sender.open_id` 时，继续使用事件自带 `sender_name/name`。
2. 飞书凭证缺失或接口查询失败时，保留原有事件字段兜底，避免阻断评论同步。
3. 飞书接口返回无姓名时，按邮箱兜底；仍为空时回退事件中的 `union_id/open_id`。

## 验证

- `uv run ruff check modules/ticket/service/ticket_message_sync_service.py modules/ticket/service/ticket_sync_notify_service.py tests/test_ticket_sync_mapping_boundary.py`
- `uv run python -m py_compile modules/ticket/service/ticket_message_sync_service.py modules/ticket/service/ticket_sync_notify_service.py tests/test_ticket_sync_mapping_boundary.py`
- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_feishu_message_sync_resolves_sender_open_id_to_user_name`
- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_bitable_pull_preserves_rich_text_newline_segments`
