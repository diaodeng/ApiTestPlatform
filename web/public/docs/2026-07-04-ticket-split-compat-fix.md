# 工单拆分兼容修复记录

## 日期

2026-07-04

## 背景

工单系统从大文件拆分为多个控制器、服务、工具模块后，出现启动期循环引用和部分功能入口丢失。拆分前逻辑可参考分支 `master_params_ticket_new`。

## 修复内容

1. 保留拆分结构，解除 `TicketService`、`TicketMessageSyncService`、`TicketSyncService` 之间的启动期循环引用。
2. 将原来为解环临时使用的函数内导入和延迟代理移除，改为独立子模块承接共享能力：`TicketCommentCoreService` 负责评论/消息底层写入，`TicketAutoClassificationService` 负责 AI 分类统计，`ticket_common_util` 负责用户上下文和版本号工具。
3. 在 `TicketSyncService` 保留拆分前私有入口兼容门面，包括 `_load_sync_config`、`_normalize_bitable_field_mappings`、`_build_bitable_pull_time_filters`、`sync_step_reason_comments` 和 `_finalize_publish_state_after_post_process` 等，实际逻辑委托到拆分后的配置、评论、群推送、AI 分类服务。
4. 消息同步和 stepReason 同步不再回调 `TicketService.upsert_synced_comment`，统一调用 `TicketCommentCoreService.upsert_synced_comment`，保持拆分前评论幂等、消息流和事件写入行为不变。
5. 手工新增、状态流转、外部同步和批量重归类仍保留拆分前 AI 分类判断、来源 hash、字段回填和人工确认保护规则，实际执行入口下沉到 `TicketAutoClassificationService`。
6. 补回拆分遗漏的 `PUT /ticket/{ticket_id:int}/rca` 接口，恢复前端“保存 RCA”功能。
7. 恢复外部创建时间解析 `_resolve_external_create_time`，避免外部同步、远端拉取和主动拉取入库时缺少提交时间口径。
8. 修复主动拉取时间覆盖：定时任务显式传入 `createdAfter/created_after` 时优先使用传入值；未传时才默认回退到当前时间前 1 小时。
9. 恢复飞书多维表格时间过滤兼容行为：无原始 filter 时使用旧口径 `or` 条件；嵌套或扁平 filter 会递归补齐已有时间条件的空值。
10. 清理拆分后遗留的未使用导入和超长行，保证工单拆分相关文件通过 `ruff`。

## 关键不变项

1. 本次未回滚拆分，不重新合并为单个大文件。
2. 本次未修改数据库结构。
3. 本次未手工修改 `web/dist` 构建产物。
4. 本次保留旧私有入口是为了兼容已有调用和测试；后续新增代码应优先直接调用拆分后的子服务。
5. 新增共享能力必须放入无上层依赖的子服务或 util，不使用函数内导入、延迟代理来掩盖依赖方向问题。

## 验证

1. `uv run ruff check modules/ticket/controller modules/ticket/service/ticket_message_sync_service.py modules/ticket/service/ticket_service.py modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_sync_config_service.py modules/ticket/service/ticket_sync_field_mapping_service.py modules/ticket/service/ticket_sync_group_push_service.py modules/ticket/service/ticket_sync_comment_service.py modules/ticket/service/ticket_comment_core_service.py modules/ticket/service/ticket_auto_classification_service.py modules/ticket/util/ticket_common_util.py tests/test_ticket_sync_mapping_boundary.py`
2. `$env:PYTHONPATH='.'; uv run python tests/test_ticket_sync_mapping_boundary.py`
3. `uv run python` 导入 `server.app` 并确认工单路由数为 88，且包含 `PUT /ticket/{ticket_id:int}/rca`。
4. `npm run build:prod`

## 后续注意

1. 拆分后的主服务兼容门面不要随意删除，除非同步迁移所有调用方和测试。
2. 工单消息同步、同步评论、AI 分类等跨链路共享能力不得反向调用主服务；需要复用时继续下沉到独立子服务。
3. 主动拉取时间过滤涉及飞书接口行为，修改前需要保留边界测试。
