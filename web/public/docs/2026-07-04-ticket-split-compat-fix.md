# 工单拆分兼容修复记录

## 日期

2026-07-04

## 背景

工单系统从大文件拆分为多个控制器、服务、工具模块后，出现启动期循环引用和部分功能入口丢失。拆分前逻辑可参考分支 `master_params_ticket_new`。

## 修复内容

1. 保留拆分结构，解除 `TicketService`、`TicketMessageSyncService`、`TicketSyncService` 之间的启动期循环引用。
2. 将原来为解环临时使用的函数内导入和延迟代理移除，改为独立子模块承接共享能力：`TicketCommentCoreService` 负责评论/消息底层写入，`TicketAutoClassificationService` 负责 AI 分类统计，`ticket_common_util` 负责用户上下文和版本号工具。
3. 清理 `TicketSyncService` 中仅为拆分兼容存在的私有入口门面，包括 `_load_sync_config`、`_normalize_bitable_field_mappings`、`_build_bitable_pull_time_filters`、`sync_step_reason_comments`、`_finalize_publish_state_after_post_process` 和 `_run_auto_ticket_ai_classification` 等。
4. 生产代码和边界测试改为直接依赖真实子服务：配置和主动拉取查询走 `TicketSyncConfigService`，评论入库走 `TicketSyncCommentService`，发布状态收敛走 `TicketSyncGroupPushService`，AI 分类统计走 `TicketAutoClassificationService`。
5. 消息同步和 stepReason 同步不再回调 `TicketService.upsert_synced_comment`，统一调用 `TicketCommentCoreService.upsert_synced_comment`，保持拆分前评论幂等、消息流和事件写入行为不变。
6. 手工新增、状态流转、外部同步和批量重归类仍保留拆分前 AI 分类判断、来源 hash、字段回填和人工确认保护规则，实际执行入口下沉到 `TicketAutoClassificationService`。
7. 补回拆分遗漏的 `PUT /ticket/{ticket_id:int}/rca` 接口，恢复前端“保存 RCA”功能。
8. 恢复外部创建时间解析 `_resolve_external_create_time`，避免外部同步、远端拉取和主动拉取入库时缺少提交时间口径。
9. 修复主动拉取时间覆盖：定时任务显式传入 `createdAfter/created_after` 时优先使用传入值；未传时才默认回退到当前时间前 1 小时。
10. 恢复飞书多维表格时间过滤兼容行为：无原始 filter 时使用旧口径 `or` 条件；嵌套或扁平 filter 会递归补齐已有时间条件的空值。
11. 删除源码目录中的 `ticket_sync_config_service.py.bak`、`ticket_sync_group_push_service.py.bak`、`ticket_sync_service.py.bak2`，避免旧入口污染代码检索和后续 AI 分析。
12. 继续拆分主动拉取边界：新增 `TicketBitablePullService` 承接飞书多维表格字段预览、记录转换、快照去重和主动拉取调度；`TicketSyncService` 删除对应主动拉取方法，不保留转发 shim。
13. `ticket_sync_controller` 的字段预览接口和 `pull_feishu_bitable_ticket_sync` 定时任务已改为直接调用 `TicketBitablePullService`；主动拉取测试同步切换到新服务。
14. 对照备份分支 `master_params_ticket_new` 保留主动拉取原始业务语义：字段映射别名归一、内部优先级兜底、当前处理人别名、`external_field_mapping` 快照、`recordId + snapshotHash` 去重、必填字段校验、富文本换行和延后后处理投递均不改变。
15. 继续拆分通知任务边界：新增 `TicketSyncNotificationJobService` 承接人员催办预览、人员催办执行和工单汇总统计通知；`TicketSyncService` 删除对应通知任务门面。
16. 固化项目实现边界规则到根目录 `AGENTS.md` 和 `web/public/docs/2026-07-04-project-implementation-boundary-rules.md`，后续实现必须先按 controller/service/dao/util/scheduler 作用域拆分。
17. 修正拆分后子服务的公开方法命名：`TicketBitablePullService` 对外可调用方法改为非 `_` 开头；`TicketSyncNotifyService` 补充公开飞书凭证、请求和时间解析方法，拆分后的子服务不再调用它的私有方法。
18. 继续拆分外部推送多维表格邮箱补齐边界：新增 `TicketExternalBitableEmailService`，承接按 `recordId` 查询飞书多维表格字段、提取三类人员邮箱并写入 `external_field_mapping` 的逻辑。
19. 继续拆分远端拉取边界：新增 `TicketRemoteSyncService`，承接远端 pending 拉取、远端 payload 转入库模型、本地 revision/time 跳过判断和 ack 回写；`pull_remote_ticket_sync` 定时任务已改为直接调用该服务，`TicketSyncService` 删除远端拉取方法，不保留转发 shim。

## 关键不变项

1. 本次未回滚拆分，不重新合并为单个大文件。
2. 本次未修改数据库结构。
3. 本次未手工修改 `web/dist` 构建产物。
4. `TicketSyncService` 不再作为拆分兼容门面；新增代码必须直接调用对应子服务。
5. 新增共享能力必须放入无上层依赖的子服务或 util，不使用函数内导入、延迟代理来掩盖依赖方向问题。

## 当前拆分评估

1. 当前拆分方向基本正确：评论幂等、消息流写入、AI 分类统计、配置归一化、主动拉取飞书查询、主动拉取编排、通知任务编排、外部推送多维表格邮箱补齐和远端拉取同步已经下沉到低层服务，解决了主服务之间相互依赖的问题。
2. 当前仍不够理想：`TicketSyncService` 仍承担外部同步入库、延后后处理、自动化和 payload 构造等多类职责，文件仍偏大。
3. 可以继续拆成独立子包，但应按调用方向渐进迁移，避免一次性移动大量文件导致接口和导入路径风险。

## 建议子包边界

1. `service/sync/`：同步编排、外部入库、延后后处理；主动拉取和远端拉取已先拆为独立服务，`TicketSyncService` 最终只保留公共编排入口。
2. `service/sync/config/`：同步配置、飞书多维表格公共配置、主动拉取 filter 和字段映射归一化。
3. `service/sync/comment/`：`stepReason`、远端评论、评论幂等写入。
4. `service/sync/notification/`：群推送、人员催办、汇总报表和飞书通知。
5. `service/ai/`：轻量 AI、AI 分析、自动分类统计、提示词解析。
6. `service/log_pull/`：日志拉取配置、日志拉取执行、日志摘要。
7. `service/core/`：工单 CRUD、状态流转、RCA、知识库和快照等核心工单能力。

迁移时不要留下只做 re-export 或转发的旧文件；若必须临时过渡，应在同一批次内同步更新所有调用方并删除过渡层。

## 验证

2026-07-04 主动拉取服务拆分后补充验证：

1. `python -m py_compile server\modules\ticket\service\ticket_bitable_pull_service.py server\modules\ticket\service\ticket_sync_service.py server\modules\ticket\controller\ticket_sync_controller.py server\module_task\scheduler_maintenance.py`
2. `cd server; uv run ruff check modules/ticket/service/ticket_bitable_pull_service.py modules/ticket/service/ticket_sync_service.py modules/ticket/controller/ticket_sync_controller.py module_task/scheduler_maintenance.py tests/test_ticket_sync_mapping_boundary.py`
3. `cd server; uv run python -m unittest tests.test_ticket_sync_mapping_boundary`

2026-07-04 远端拉取服务拆分后补充验证：

1. `cd server; uv run python -m py_compile modules/ticket/service/ticket_remote_sync_service.py modules/ticket/service/ticket_sync_service.py module_task/scheduler_maintenance.py tests/test_ticket_sync_mapping_boundary.py`
2. `cd server; uv run ruff check modules/ticket/service/ticket_remote_sync_service.py modules/ticket/service/ticket_sync_service.py module_task/scheduler_maintenance.py tests/test_ticket_sync_mapping_boundary.py`
3. `cd server; uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
4. `rg -n "TicketRemoteSyncService\._|TicketBitablePullService\._|TicketExternalBitableEmailService\._|TicketSyncNotificationJobService\._|TicketSyncService\.sync_remote_pending_tickets" server server\tests -g "*.py"`

历史拆分验证：

1. `uv run ruff check modules/ticket/controller modules/ticket/service/ticket_message_sync_service.py modules/ticket/service/ticket_service.py modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_sync_config_service.py modules/ticket/service/ticket_sync_field_mapping_service.py modules/ticket/service/ticket_sync_group_push_service.py modules/ticket/service/ticket_sync_comment_service.py modules/ticket/service/ticket_comment_core_service.py modules/ticket/service/ticket_auto_classification_service.py modules/ticket/util/ticket_common_util.py tests/test_ticket_sync_mapping_boundary.py`
2. `$env:PYTHONPATH='.'; uv run python tests/test_ticket_sync_mapping_boundary.py`
3. `uv run python` 导入 `server.app` 并确认工单路由数为 88，且包含 `PUT /ticket/{ticket_id:int}/rca`。
4. `npm run build:prod`

## 后续注意

1. 工单消息同步、同步评论、AI 分类等跨链路共享能力不得反向调用主服务；需要复用时继续下沉到独立子服务。
2. 主动拉取时间过滤涉及飞书接口行为，修改前需要保留边界测试。
3. 后续移动到子包时，优先移动低层无反向依赖模块，再迁移调用方，最后删除旧路径文件。
