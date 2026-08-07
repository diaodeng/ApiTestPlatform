# 多维表格主动拉取必填字段模型校验

## 变更日期

- 2026-06-24

## 结论

- 飞书多维表格主动拉取会按“外部工单字段模型”中 `required=true` 的字段做记录级必填校验。
- 字段不全的记录会在转换同步模型阶段失败，不会调用 `sync_external_ticket` 入库，也不会触发延后后处理和自动群消息。
- 旧字段 `externalSyncRequiredFields` 仅作为历史兼容配置保留；主动拉取运行时不再优先读取它，避免和外部工单字段模型漂移。

## 问题背景

- 主动拉取历史上通过 `externalSyncRequiredFields` 获取必填字段。
- 页面和文档已将“外部工单字段模型”作为字段全集与必填标记的主配置，如果历史 `externalSyncRequiredFields` 与字段模型不一致，可能导致字段不全的多维记录被放行。

## 关键实现

- `TicketSyncService.run_bitable_pull_services()` 直接调用：

```python
required_fields = cls._derive_required_fields_from_external_field_model(config.get("externalFieldModel"))
```

- `_build_bitable_pull_sync_object()` 继续执行记录级校验：
  - 缺少必填字段时记录 warning 日志，包含 `missing_required_fields`
  - 返回 `None`
  - 调度汇总计入 `failedCount`
  - 不调用 `sync_external_ticket`
  - 不调用 `dispatch_deferred_sync_post_process_task`

## 验证

- 新增测试覆盖：即使旧 `externalSyncRequiredFields` 放宽，只要 `externalFieldModel.fields` 中 `ticketModle.required=true`，缺少模块的主动拉取记录也不会入库或触发后处理。
- 验证命令：

```bash
uv run ruff check modules/ticket/service/ticket_sync_service.py tests/test_ticket_sync_mapping_boundary.py
uv run python -m unittest tests.test_ticket_sync_mapping_boundary
```
