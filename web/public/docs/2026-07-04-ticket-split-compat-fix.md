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
20. 继续拆分外部入库 payload 构造边界：新增 `TicketSyncPayloadService`，承接 `build_upsert_payload`、`build_meta`、`attach_meta`、`resolve_external_create_time`、`merge_external_text_fields` 和自动拉日志日期解析；`TicketSyncService` 删除对应私有方法，不保留转发 shim，只在入库、延后后处理、pending/ack 和自动化链路中直接调用新服务公开方法。
21. 继续拆分延后后处理边界：新增 `TicketSyncPostProcessService` 承接 Celery 可用性探测、延后任务投递、本地后台/Celery 运行入口、系统用户 payload 归一化和延后后处理执行主体；控制器、主动拉取和 Celery 任务已改为直接调用该服务，`TicketSyncService` 删除对应入口。
22. 为避免延后后处理服务反向依赖主同步服务，新增 `TicketSyncAutomationService` 承接字段识别、同步自动化步骤状态、相似工单检索、自动拉日志和自动 AI 分析提交；`TicketSyncService` 主入库链路与 `TicketSyncPostProcessService` 均直接调用该服务。
23. 将工单服务按依赖关系移动到独立子包：`service/sync`、`service/ai`、`service/log_pull`、`service/core`、`service/collaboration`、`service/notification`、`service/stats`；所有调用方和测试均改为新路径，旧 `service/ticket_*.py` 顶层服务文件删除，不保留 re-export 或转发 shim。
24. 继续拆分同步交付边界：新增 `TicketSyncDeliveryService` 承接 `syncSummary` 构造、消费者状态更新、`/ticket/sync/pending` 拉取和 `/ticket/sync/ack` 回执；控制器直接调用该服务，`TicketSyncService` 删除 pending/ack 入口。
25. 继续拆分批量重归类边界：新增 `TicketBatchReclassificationService` 承接 `/ticket/sync/auto-category/reclassify`、`/ticket/sync/auto-category/stats`、正则批量归类、AI 批量归类调度和未归类统计；控制器直接调用新服务，`TicketSyncService` 删除对应入口。

## 关键不变项

1. 本次未回滚拆分，不重新合并为单个大文件。
2. 本次未修改数据库结构。
3. 本次未手工修改 `web/dist` 构建产物。
4. `TicketSyncService` 不再作为拆分兼容门面；新增代码必须直接调用对应子服务。
5. 外部同步持久化字段构造已下沉到 `TicketSyncPayloadService`；后续项目/模块、来源快照、revision、log_pull_hints 等入库 payload 规则应优先修改该服务，不再回填到 `TicketSyncService`。
6. 延后后处理调度和执行已下沉到 `TicketSyncPostProcessService`；Celery 任务、FastAPI 后台任务和主动拉取回退任务不得再调用 `TicketSyncService` 的旧入口。
7. 字段识别和自动化执行已下沉到 `TicketSyncAutomationService`；后续新增项目/模块/人员识别、自动拉日志或自动 AI 分析规则应优先修改该服务。
8. 新增共享能力必须放入无上层依赖的子服务或 util，不使用函数内导入、延迟代理来掩盖依赖方向问题。
9. 工单服务当前已按子包组织，新增或修改调用方必须使用 `modules.ticket.service.<子包>.<服务文件>` 路径；不得恢复 `modules.ticket.service.ticket_*` 旧入口。
10. 内网消费者交付状态已下沉到 `TicketSyncDeliveryService`；后续 pending 拉取、ack 回执、`delivered_revision` 推进和 `syncSummary` 字段规则应优先修改该服务，不再回填到 `TicketSyncService`。
11. 批量重归类和未归类统计已下沉到 `TicketBatchReclassificationService`；后续手动重归类、正则归类批处理和统计入口不得再回填到 `TicketSyncService`。

## 当前拆分评估

1. 当前拆分方向基本正确：评论幂等、消息流写入、AI 分类统计、配置归一化、主动拉取飞书查询、主动拉取编排、通知任务编排、外部推送多维表格邮箱补齐和远端拉取同步已经下沉到低层服务，解决了主服务之间相互依赖的问题。
2. 当前已完成第一轮包级收敛：同步、AI、日志拉取、核心工单、协作、通知和统计服务不再全部堆在 `service/` 根包。
3. 当前仍不够理想：`TicketSyncService` 仍承担外部同步入库主编排和外部请求归一化等职责，但 payload 构造、延后后处理、字段识别、同步自动化、pending 拉取、ack 回执、批量重归类和未归类统计已拆入独立服务；后续继续拆分时应在 `service/sync/` 内按更细职责迁移。

## 当前子包边界

1. `service/sync/`：外部同步入库、同步配置、字段映射、飞书主动拉取、远端拉取、同步交付、延后后处理、同步自动化、群推送和同步通知任务。
2. `service/ai/`：AI 分析、轻量 AI、自动分类统计、提示词解析和相似度向量能力。
3. `service/log_pull/`：日志拉取执行、日志记录查看和日志内容处理。
4. `service/core/`：工单 CRUD、状态流转、RCA、知识库、导入和快照等核心工单能力。
5. `service/collaboration/`：评论幂等写入、飞书话题消息同步和飞书事件监听。
6. `service/notification/`：通用工单通知发送能力。
7. `service/stats/`：专题工单统计任务。

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

2026-07-04 延后后处理与同步自动化拆分后补充验证：

1. `python -m compileall server/modules/ticket/service/ticket_sync_service.py server/modules/ticket/service/ticket_sync_post_process_service.py server/modules/ticket/service/ticket_sync_automation_service.py server/modules/ticket/service/ticket_sync_payload_service.py server/modules/ticket/controller/ticket_sync_controller.py server/modules/ticket/service/ticket_bitable_pull_service.py server/module_task/celery_tasks.py`
2. `cd server; uv run ruff check modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_sync_post_process_service.py modules/ticket/service/ticket_sync_automation_service.py modules/ticket/service/ticket_sync_payload_service.py modules/ticket/controller/ticket_sync_controller.py modules/ticket/service/ticket_bitable_pull_service.py module_task/celery_tasks.py`
3. `rg -n "TicketSyncService\.run_deferred|TicketSyncService\.dispatch|TicketSyncService\.CELERY|_detect_fields|_execute_deferred_sync_post_process|_build_system_current_user|_normalize_current_user_payload|_mark_automation_step|_collect_text|_extract_pattern" server/modules/ticket server/module_task -S`

2026-07-04 服务子包组织后补充验证：

1. `cd server; uv run python -m compileall modules/ticket module_task tests`
2. `cd server; uv run ruff check server.py module_admin/service/ai_config_service.py module_admin/service/ai_prompt_template_service.py module_task/celery_tasks.py module_task/scheduler_maintenance.py modules/ticket/controller/ticket_ai_controller.py modules/ticket/controller/ticket_config_controller.py modules/ticket/controller/ticket_controller.py modules/ticket/controller/ticket_crud_controller.py modules/ticket/controller/ticket_log_pull_controller.py modules/ticket/controller/ticket_sync_controller.py modules/ticket/util/ticket_feishu_bitable_util.py tests/test_ticket_sync_mapping_boundary.py tests/test_ticket_topic_stats_service.py modules/ticket/service/ai modules/ticket/service/collaboration modules/ticket/service/core modules/ticket/service/log_pull modules/ticket/service/notification modules/ticket/service/sync`
3. `rg -n "from modules\.ticket\.service\.ticket_|import modules\.ticket\.service\.ticket_|modules\.ticket\.service\.ticket_" server web/public/docs/2026-07-04-ticket-split-compat-fix.md wiki/entities/services/ticket-domain.md wiki/flows/ticket-external-sync-flow.md -S`

2026-07-04 同步交付服务拆分后补充验证：

1. `cd server; uv run ruff check modules/ticket/service/sync/ticket_sync_service.py modules/ticket/service/sync/ticket_sync_delivery_service.py modules/ticket/controller/ticket_sync_controller.py tests/test_ticket_sync_mapping_boundary.py`
2. `cd server; uv run python -m compileall modules/ticket/service/sync modules/ticket/controller tests/test_ticket_sync_mapping_boundary.py tests/test_ticket_topic_stats_service.py`
3. `cd server; uv run python -m unittest tests.test_ticket_sync_mapping_boundary tests.test_ticket_topic_stats_service`
4. `rg -n "TicketSyncService\.(pull_pending_tickets|ack_sync_delivery|extract_sync_summary)|_update_consumer_state|modules\.ticket\.service\.ticket_" server -S`

2026-07-04 批量重归类服务拆分后补充验证：

1. `cd server; uv run python -m py_compile modules/ticket/service/sync/ticket_batch_reclassification_service.py modules/ticket/service/sync/ticket_sync_service.py modules/ticket/controller/ticket_sync_controller.py tests/test_ticket_sync_mapping_boundary.py`
2. `cd server; uv run ruff check modules/ticket/service/sync/ticket_batch_reclassification_service.py modules/ticket/service/sync/ticket_sync_service.py modules/ticket/controller/ticket_sync_controller.py tests/test_ticket_sync_mapping_boundary.py`
3. `cd server; uv run python -m unittest tests.test_ticket_sync_mapping_boundary`
4. `rg -n "TicketSyncService\.(batch_reclassify_ticket_categories_services|get_uncategorized_ticket_statistics_services)|_run_auto_ticket_category_classification|TicketSyncService\._run_auto_ticket_category_classification" server web/public/docs wiki -S`

历史拆分验证：

1. `uv run ruff check modules/ticket/controller modules/ticket/service/ticket_message_sync_service.py modules/ticket/service/ticket_service.py modules/ticket/service/ticket_sync_service.py modules/ticket/service/ticket_sync_config_service.py modules/ticket/service/ticket_sync_field_mapping_service.py modules/ticket/service/ticket_sync_group_push_service.py modules/ticket/service/ticket_sync_comment_service.py modules/ticket/service/ticket_comment_core_service.py modules/ticket/service/ticket_auto_classification_service.py modules/ticket/util/ticket_common_util.py tests/test_ticket_sync_mapping_boundary.py`
2. `$env:PYTHONPATH='.'; uv run python tests/test_ticket_sync_mapping_boundary.py`
3. `uv run python` 导入 `server.app` 并确认工单路由数为 88，且包含 `PUT /ticket/{ticket_id:int}/rca`。
4. `npm run build:prod`

## 后续注意

1. 工单消息同步、同步评论、AI 分类等跨链路共享能力不得反向调用主服务；需要复用时继续下沉到独立子服务。
2. 主动拉取时间过滤涉及飞书接口行为，修改前需要保留边界测试。
3. 后续移动到子包时，优先移动低层无反向依赖模块，再迁移调用方，最后删除旧路径文件。
