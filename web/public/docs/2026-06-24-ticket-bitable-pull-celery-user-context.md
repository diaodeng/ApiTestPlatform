# 多维表格主动拉取 Celery 用户上下文修复

## 变更日期

- 2026-06-24

## 结论

- 修复飞书多维表格主动拉取入库成功后，延后后处理投递 Celery 时系统用户上下文不完整导致 `CurrentUserModel` 校验失败的问题。
- 定时任务场景现在会构造完整系统用户载荷：`permissions=[]`、`roles=[]`、`user.userId=0`、`user.userName=system`。
- 延后后处理入口兼容历史只包含 `user` 的任务载荷，并把旧的 `user_id/user_name/nick_name` 转成 Pydantic alias 可识别的 `userId/userName/nickName`。
- 主动拉取字段映射的目标字段兼容 `moduleName/module_name/ticketModel/ticket_model`，统一归一为外部同步必填字段 `ticketModle`。

## 问题现象

日志表现为主动拉取入库后已投递 Celery，但 Celery 执行延后后处理时报错：

```text
2 validation errors for CurrentUserModel
permissions Field required
roles Field required
```

随后后处理链路未继续执行，影响自动 AI、自动化识别、相似工单向量化和群推送等延后动作。

## 根因

- `CurrentUserModel` 要求 `permissions` 和 `roles` 必填。
- 主动拉取定时任务没有真实登录用户，旧逻辑只传 `{"user": {...}}` 给 Celery。
- `UserInfoModel` 使用 camelCase alias，旧 payload 中的 `user_id/user_name/nick_name` 即使补齐后也不会正确写入 `user.user_id/user.user_name`。

## 修复内容

- `TicketSyncService._build_system_current_user_payload()` 统一生成可序列化系统用户载荷。
- `TicketSyncService._build_system_current_user()` 统一生成同步入库阶段使用的系统用户模型。
- `TicketSyncService._normalize_current_user_payload()` 统一补齐并兼容历史用户载荷。
- 主动拉取入库、Celery 投递、本地后台回退和延后后处理反序列化统一复用上述方法。
- `TicketSyncService._normalize_bitable_pull_target_field()` 统一处理主动拉取目标字段别名，避免配置使用 `moduleName` 时被必填校验误判为缺少 `ticketModle`。

## 验证

- `uv run ruff check modules/ticket/service/ticket_sync_service.py tests/test_ticket_sync_mapping_boundary.py`
- 使用 `uv run python -` 直接校验系统用户 payload 和历史 user-only payload 均可通过 `CurrentUserModel.model_validate`，且 `user_id/user_name` 能正确写入。
- `uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
