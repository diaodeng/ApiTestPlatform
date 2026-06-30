---
title: 操作日志
type: log
source_type: mixed
created: 2026-05-20
updated: 2026-07-01
---

# 操作日志

## [2026-07-01] INGEST-CODE | 工单细分问题类型与趋势统计
- 触发：用户希望固定枚举化“内存泄露”“280开头券为纸质券规则说明”等细分原因，并按时间趋势展示支持类、Bug、非 Bug、模块和具体问题变化。
- 架构层：工单域 / 分类统计 / 轻量 AI 自动分类 / Web 统计页
- 创建的页面：`web/public/docs/2026-07-01-ticket-problem-pattern-trend-statistics.md`、`server/sql/20260701_ticket_problem_pattern_columns.sql`
- 更新的页面：`server/modules/ticket/entity/do/ticket_do.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_light_ai_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/config/get_db.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/statistics/index.vue`、`web/src/views/ticket/syncAutomation/index.vue`、`wiki/entities/services/ticket-domain.md`、`wiki/entities/data-models/ticket-core-models.md`、`wiki/entities/enums/ticket-enums.md`
- 变更传播链：`ticket.sync.automation.statClassification.problemPatterns` -> AI 分类候选枚举 -> `ticket.problem_pattern_*` 主表字段 -> 工单列表/编辑/状态流转 -> 汇总统计与趋势统计。
- 关键结论：细分原因不再使用自由标签作为主统计口径；AI 只允许从启用的固定 `problemPatterns` 候选中选择。人工确认的细分问题不被后续 AI 覆盖。趋势接口按事件时间实时计算当前分类和周期末未关闭存量，正式周报如需历史不变更，应后续增加统计快照。

## [2026-06-30] INGEST-CODE | 后台任务与定时任务日志 tid 补齐
- 触发：用户反馈 HTTP 请求已有日志 tid，但定时任务触发执行、工单同步延后后台过程仍显示 `[-]`，无法串联一次执行。
- 架构层：日志上下文 / Celery 调度 / 工单同步自动化
- 创建的页面：`web/public/docs/2026-06-30-background-task-trace-id.md`
- 更新的页面：`server/context/request_context.py`、`server/middlewares/cors_middleware.py`、`server/module_task/celery_tasks.py`、`server/module_task/celery_job_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：HTTP `X-Request-Id` / Celery Worker 自动生成 `job-xxxxxxxx` -> `context.request_context` -> loguru patcher -> 定时任务、工单延后后处理、本地后台任务日志统一输出 tid。
- 关键结论：非 HTTP 入口必须显式设置 contextvars；定时任务在 Worker 执行时生成 tid，避免 Beat 同步时生成后被周期复用。工单外部同步延后任务投递 Celery 或回退本地后台时都传递当前 tid，发布后需重启 Celery Worker 以加载新任务签名。

## [2026-06-28] INGEST-CODE | 帮助中心文档自动索引
- 触发：用户反馈 `web/src/views/about/about.vue` 只能查看手写菜单中的少量帮助文档，后续自动增加的业务说明和配置说明无法方便查看。
- 架构层：Web 控制台 / 帮助文档 / 前端构建插件
- 创建的页面：`web/public/docs/2026-06-28-help-docs-auto-index.md`
- 更新的页面：`web/src/views/about/about.vue`、`web/vite/plugins/docs-index.js`、`web/vite/plugins/index.js`、`web/public/docs/update_history.md`、`wiki/entities/components/frontend-bootstrap.md`、`wiki/entities/services/web-feature-domains.md`
- 变更传播链：`web/public/docs/*.md` -> Vite 启动/构建扫描 -> `docs-index.json` -> 帮助中心搜索与分类菜单 -> Markdown 渲染组件展示。
- 关键结论：浏览器不能直接枚举 `public/docs` 目录，因此自动发现必须放在构建期或后端接口；本次选择前端 Vite 插件，避免增加后端接口。后续新增 Markdown 文档只需放入 `web/public/docs`，重新启动开发服务或执行生产构建后即可在帮助中心查看。

## [2026-06-27] INGEST-CODE | 工单排查过程消息同步用户名解析
- 触发：用户反馈最近实现的工单排查过程消息同步中，飞书会话跟帖消息同步到当前系统和飞书多维表格时，用户记录成飞书内部 ID，希望通过飞书接口查询用户名。
- 架构层：工单域 / 飞书话题评论入站 / 工单评论 / 多维表格排查过程
- 创建的页面：`web/public/docs/2026-06-27-ticket-message-sync-user-name.md`
- 更新的页面：`server/modules/ticket/service/ticket_message_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-26-ticket-message-sync.md`、`web/public/docs/2026-06-27-ticket-message-sync-user-name.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：飞书消息事件 `sender.open_id` -> 飞书通讯录用户详情查询 -> `sender_display_name` -> `ticket_comment.user_name` 与多维表格 `stepReason` 追加 `{user}`。
- 关键结论：评论同步不是工单主体同步；入站跟帖消息需要在落库和写回多维前统一解析发送人展示名。凭证优先使用 `feishuAuth`，群推送和多维配置只作为兜底；查询失败不阻断同步，只回退事件自带名称或 ID。飞书正文 `@_user_1` 必须结合 `mentions` 解析，系统显示 `@用户名`，附件保留人员 ID；多维 Text 富文本片段中的 `mention_user_id` 也要带入评论附件，才能在系统、飞书群和多维表格之间恢复真实 @ 样式。

## [2026-06-26] INGEST-CODE | 多维表格主动拉取富文本换行保留
- 触发：用户反馈主动拉取多维表格数据时，换行符被处理成 `{"text": "\n", "type": "text"}` 或空文本片段，导致内容格式丢失、描述挤在一起、排查过程评论分割不正确。
- 架构层：工单域 / 飞书多维表格主动拉取 / 字段映射 / 同步评论
- 创建的页面：`web/public/docs/2026-06-26-ticket-bitable-pull-rich-text-newline.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：飞书富文本片段数组 -> `_normalize_bitable_record_scalar` 富文本识别 -> 描述/排查过程保留真实换行 -> `parse_step_reason_segments` 按日期行拆分评论。
- 关键结论：富文本片段数组必须按片段顺序拼接，换行片段保留为真实 `\n`，空文本片段不落为 JSON 文本；普通多选和人员数组继续走原分隔符拼接逻辑。

## [2026-06-25] INGEST-CODE | 日志拉取下载链接复制
- 触发：用户反馈工单详情页日志拉取列表“下载原始包”和日志拉取管理页“下载日志”无法复制原始日志下载链接，需要能粘贴到邮件。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 下载链接
- 创建的页面：`web/public/docs/2026-06-25-ticket-log-pull-copy-download-link.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`
- 变更传播链：日志拉取记录 `commandResultUrl/storagePath` -> 前端下载策略解析 -> “复制链接”入口 -> 邮件或 IM 粘贴。
- 关键结论：原始压缩包优先复制外部 `commandResultUrl`；管理页按“下载日志”实际策略复制 HTTP 归档、原始地址或系统下载接口。本地/FTP 归档复制的是鉴权接口地址，访问者需要系统登录态。

## [2026-06-25] INGEST-CODE | 多维表格主动拉取群消息人员解析与日志
- 触发：用户反馈 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 同步后推送消息有概率获取不到人员信息，并要求发送消息日志记录消息内容。
- 架构层：工单域 / 飞书多维表格主动拉取 / 群消息通知 / 飞书人员 @ 解析
- 创建的页面：`web/public/docs/2026-06-25-ticket-bitable-pull-mention-log-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`
- 变更传播链：`bitablePull.fieldMappings` 人员字段 -> `_build_bitable_pull_field_mapping_from_record` 提取姓名/邮箱 -> `extraData.external_field_mapping` -> `_resolve_ticket_person_email` -> 飞书邮箱查 `open_id` -> 群消息渲染与发送日志。
- 关键结论：人员信息应优先来自拉取到的数据中的人员字段邮箱；本地系统用户只作为姓名兜底。若飞书人员字段没有邮箱且本地也无用户邮箱，则无法解析 `open_id`，但现在日志会记录最终正文和解析明细。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取必填字段模型校验
- 触发：用户确认主动拉取多维表格数据是否按“外部工单字段模型”做必填字段校验，并要求字段不全时不要入库或发群消息。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部字段模型 / 群消息后处理
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-required-field-model.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`externalFieldModel.fields[].required` -> `run_bitable_pull_services` 必填字段推导 -> `_build_bitable_pull_sync_object` 记录级校验 -> 失败记录不调用 `sync_external_ticket` / `dispatch_deferred_sync_post_process_task`。
- 关键结论：主动拉取现在直接以外部工单字段模型为必填校验口径；字段不全只计入 `failedCount` 和 warning 日志，不入库、不触发自动群消息。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取优先级与人员字段兜底
- 触发：用户反馈多维表格主动拉取中对方优先级和内部优先级反了，且部分内部负责人、当前处理人为空；要求内部优先级无值时使用外部优先级，不影响外部推送逻辑。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部同步入库字段映射
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-priority-person-fallback.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`bitablePull.fieldMappings` -> `_build_bitable_pull_sync_object` 主动拉取专用归一化 -> `TicketExternalSyncUpsertModel` 顶层字段与 `extraData.external_field_mapping` -> `_detect_fields/_build_upsert_payload` 入库。
- 关键结论：问题位置不在外部推送 controller，而在主动拉取绕过 controller 归一化后直接构造同步模型；本次只补主动拉取转换层，外部推送逻辑不变。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取强制同步与字段保留
- 触发：用户要求主动拉取多维表格数据支持强制同步，并反馈入库项目、模块、内部负责人为空，执行完成后未翻译。
- 架构层：工单域 / 飞书多维表格主动拉取 / 外部同步入库 / 翻译自动化
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-force-sync-field-translate.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/module_task/scheduler_maintenance.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`forceSync/force_sync` -> 主动拉取运行配置 -> 绕过 `snapshotHash` 跳过 -> 重新入库与延后后处理；字段映射 -> `extraData.external_field_mapping` + 顶层 `projectName/moduleName/internalOwnerName` -> 项目/模块/人员识别；`automation.autoTranslate` -> 外部同步翻译决策 -> 主链路与延后后处理一致执行。
- 关键结论：强制同步只绕过去重，不扩大飞书查询范围；历史数据重拉仍需配合 `createdAfter/filterFormula/viewId`。主动拉取来源字段为空时不会凭空补出项目、模块或负责人。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取 Celery 用户上下文修复
- 触发：用户反馈多维表格主动拉取任务入库后，延后后处理 Celery 报 `CurrentUserModel.permissions/roles Field required`，随后记录转换又提示缺少 `ticketModle`。
- 架构层：工单域 / 飞书多维表格主动拉取 / Celery 延后后处理 / 用户上下文
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-pull-celery-user-context.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`run_bitable_pull_services` 定时任务系统用户 -> 完整 `CurrentUserModel` payload -> Celery `run_deferred_sync_post_process` -> 自动 AI、自动化识别、相似工单向量化、群推送等延后动作继续执行；字段映射目标别名 -> `ticketModle` 规范字段 -> 必填校验。
- 关键结论：系统用户 payload 必须包含 `permissions=[]`、`roles=[]`，且用户字段要使用 Pydantic alias `userId/userName/nickName`；历史只包含 `user_id/user_name/nick_name` 的队列任务在入口处转换兼容。`moduleName/module_name/ticketModel/ticket_model` 目标字段会归一为 `ticketModle`，但来源字段为空仍会跳过记录。

## [2026-06-23] INGEST-CODE | 日志拉取参数示例与日期预填
- 触发：用户要求日志拉取弹窗支持从参数示例下拉填入当前参数，并在工单提取门店、POS 编号时同步提取日期预填到 modifyTime。
- 架构层：工单域 / 日志拉取 / 参数配置 / 工单同步 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-23-ticket-log-pull-parameter-examples.md`
- 更新的页面：`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/service/ticket_log_pull_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/src/components/ticket/LogPullConfigFields.vue`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/logPullRecord/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：`ticket.logPull.parameterExamples` -> `/ticket/log-pull/vendor-store-options.parameterExamples` -> `LogPullConfigFields` 参数示例下拉 -> 当前参数写入 `modifyTime/path`；`extra_data.log_pull_hints.modifyTime` -> 添加日志拉取弹窗预填。
- 关键结论：参数示例配置为 `[{name,value}]` 列表；日志类型填入日期参数，数据库类型填入路径参数，工单日期只在存在有效值时覆盖预填。

## [2026-06-23] INGEST-CODE | 工单日志拉取记录独立查看
- 触发：用户反馈同一工单有多条日志拉取记录时，点击某条记录查看日志会显示之前查看过的记录；同时要求明确日志拉取成功后的下载/解压行为，以及 AI 分析使用哪条日志记录。
- 架构层：工单域 / 日志拉取 / 日志查看 / AI 分析任务提交
- 创建的页面：`web/public/docs/2026-06-23-ticket-log-record-isolated-view.md`、`wiki/flows/ticket-log-record-isolated-view.md`
- 更新的页面：`server/modules/ticket/service/ticket_log_service.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：日志拉取记录行 -> `recordId` 传入日志准备 -> `data/logs/ticket_{ticketId}/record_{recordId}` 独立目录 -> 搜索/上下文/异常摘要继续携带 `recordId`；从记录查看器发起 AI 分析 -> 请求携带 `logPullRecordId`
- 关键结论：日志拉取成功会下载压缩包并按记录归档；有时间范围时截取正文入库，无时间范围时只归档整包。AI 分析请求未指定记录时取工单最新日志记录，版本号缺失时再用最近成功记录兜底。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取字段预览元数据化
- 触发：用户反馈飞书多维表格主动拉取中“读取表格字段”失败，日志显示 `records=0`；昨天可读，当前因运行时默认时间窗口/过滤条件下无记录导致样例记录字段推断为空。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-field-preview-metadata.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`fields-preview` -> `TicketSyncNotifyService.query_bitable_fields` -> 飞书字段元数据接口；元数据失败 -> 清空 `filterFormula/createdAfter` 后样例记录兜底；主动拉取定时任务过滤逻辑不变。

## [2026-06-23] INGEST-CODE | 工单多维表格配置保存态与运行态拆分
- 触发：用户反馈填写“多维表格公共配置”后，“飞书多维表格主动拉取”的对应配置项也会被自动填上，要求多维主动拉取有独立配置时用独立配置，没有才用表格公共配置，并梳理外部推送、内部拉取、主动拉取、手动新增/编辑的配置边界和翻译配置关系。
- 架构层：工单域 / 同步自动化配置 / 飞书多维表格集成 / 翻译自动化
- 创建的页面：`web/public/docs/2026-06-23-ticket-bitable-config-scope.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-23-ticket-bitable-config-scope.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`ticket.sync.automation.bitableCommon` -> 运行时多维查询配置解析 -> 外部推送邮箱补齐 / 飞书多维表格主动拉取 / 按人催办 / 汇总统计；页面回显不再被公共配置污染。
- 追加：翻译配置边界已写入文档；外部推送、内部拉取、主动拉取、手动新增/编辑分别有自己的场景开关，但共用 AI 配置中心的翻译总开关、Provider 和 Prompt。
- 风险：历史库中已经被旧逻辑写入独立配置段的公共值不会自动清理，避免误删用户真实独立配置；需在页面手动清空一次后保存。

## [2026-06-23] INGEST-CODE | 工单 AI Agent 异常反馈修复
- 触发：用户反馈发起工单 AI 分析时 Agent 未连接或连接异常，服务端已有报错但 Web 页面只显示 `{}` 或没有真实失败原因。
- 架构层：工单域 / AI 分析任务 / Agent 连接校验 / Web 错误提示
- 创建的页面：`web/public/docs/2026-06-23-ticket-ai-agent-error-feedback.md`
- 更新的页面：`server/modules/ticket/service/ticket_ai_analysis_service.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/index.vue`、`web/src/utils/request.js`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：AI 分析提交 -> 服务端 Agent 在线校验 -> 前端响应错误归一化 -> 提交/重试短轮询任务终态 -> 失败原因弹窗展示
- 验证：`uv run ruff check modules/ticket/service/ticket_ai_analysis_service.py`、`npm run build:prod` 均通过；前端构建仍有既有 `config.js`、`eval` 和 chunk 体积警告。
- 总共涉及页面：8

## [2026-06-22] INGEST-CODE | 工单日志查看器交互与编码兼容优化
- 触发：用户要求工单日志搜索结果和上下文窗口支持全屏/最小化，修复上下文翻页重复、搜索结果数量受限、中文乱码和上下文滚动查看问题。
- 架构层：工单域 / 日志查看 / Web 控制台 / 日志服务
- 创建的页面：`web/public/docs/2026-06-22-ticket-log-viewer-usability.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`server/modules/ticket/service/ticket_log_service.py`、`server/modules/ticket/entity/vo/ticket_log_pull_vo.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：日志查看弹窗 -> 搜索结果上限与面板状态 -> 点击命中按需加载上下文 -> 后端非重叠翻页指针 -> 编码兼容读取与中文关键字搜索
- 验证：`uv run ruff check modules/ticket/service/ticket_log_service.py modules/ticket/entity/vo/ticket_log_pull_vo.py`、GB18030 中文日志上下文/搜索小样本、`npm run build:prod` 均通过。
- 总共涉及页面：7

## [2026-06-22] INGEST-CODE | 工单入库原文保留与 AI 分析版本号兜底
- 触发：用户要求项目、模块匹配失败时保留原文；后续数据无版本号时不清空已有版本；手动发起 AI 分析可选版本号，未选时从日志提取并回写后发起分析。
- 架构层：工单域 / 外部同步入库 / 工单编辑 / 日志拉取 / AI 分析任务提交
- 创建的页面：`web/public/docs/2026-06-22-ticket-ingest-version-ai-fallback.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/service/ticket_ai_analysis_service.py`、`server/modules/ticket/service/ticket_log_pull_service.py`、`server/modules/ticket/dao/ticket_log_pull_dao.py`、`server/modules/ticket/entity/vo/ticket_vo.py`、`web/src/views/ticket/index.vue`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：外部同步识别 -> `_build_upsert_payload` 原文保留 -> 工单编辑版本保护 -> `TicketAiAnalysisService._ensure_version_key_for_analysis` 日志提取回填 -> AI 分析任务提交
- 验证：通过本次相关 6 个边界测试；整文件测试仍有既有 `bitableCommon.pageSize` 断言失败，未纳入本次改动范围。
- 总共涉及页面：13

## [2026-06-22] INGEST-CODE | 相似工单支持详情跳转
- 触发：用户要求工单详情页中的相似工单可跳转查看，支持原飞书详情 URL 和当前系统详情页；当前系统详情原为弹窗，需要通过 URL 拼接工单号独立打开。
- 架构层：工单域 / Web 控制台 / 工单详情弹窗 / 相似工单
- 创建的页面：`web/public/docs/2026-06-22-ticket-similar-detail-links.md`
- 更新的页面：`web/src/router/index.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：相似工单卡片 -> `openSystemTicketDetail` 生成 `#/ticket/detail/:ticketId` -> 隐藏路由复用工单页并自动打开详情弹窗；外部链接继续走 `resolveTicketDetailUrl` -> `openTicketLink`
- 总共涉及页面：5

## [2026-06-22] INGEST-CODE | 多维表格主动拉取创建时间窗口
- 触发：用户要求定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 默认查询当前时间前 1 小时之后的数据，指定时间时按指定时间之后的数据查询。
- 架构层：工单域 / 飞书多维表格主动拉取 / 任务调度
- 创建的页面：`web/public/docs/2026-06-22-ticket-bitable-pull-created-after.md`
- 更新的页面：`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`pull_feishu_bitable_ticket_sync` 补齐 `createdAfter` -> `TicketSyncService.run_bitable_pull_services` 按飞书记录创建时间过滤 -> 外部同步入库链路
- 总共涉及页面：5

## [2026-06-22] INGEST-CODE | 修复飞书多维表格记录详情链接
- 触发：用户反馈 `TicketSyncService._build_bitable_record_url` 使用多维表格搜索结果中的 `record_id` 拼接 URL 无法访问，真实可访问地址需要飞书记录详情 URL。
- 架构层：工单域 / 飞书多维表格集成 / 按人催办通知
- 创建的页面：`web/public/docs/2026-06-22-ticket-bitable-record-url-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketSyncNotifyService.query_bitable_records` 搜索记录 -> `records/batch_get(with_shared_url=true)` 批量补齐 `shared_url` -> `TicketSyncService._build_bitable_pull_sync_object` / `TicketSyncNotifyService._collect_person_overdue_data` -> 工单 `ticket_url` / 来源 `recordUrl` / 催办 `detailUrl`
- 追加：已用 dev 环境真实参数只读实测，`records/search` 未返回链接，但 `records/batch_get` 可稳定返回 `https://duodian.feishu.cn/record/...` 形式的 `shared_url`；补查后 31 条记录全部成功补齐。
- 总共涉及页面：7

## [2026-06-18] INGEST-CODE | 工单统计项目模块多选筛选
- 触发：用户要求工单统计页面顶部增加按项目、模块筛选，并支持多选。
- 架构层：工单域 / Web 控制台 / 统计接口
- 创建的页面：`web/public/docs/2026-06-18-ticket-statistics-project-module-multiselect.md`
- 更新的页面：`web/src/views/ticket/statistics/index.vue`、`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：统计页多选筛选 -> `TicketStatisticsQueryModel.projectIds/moduleIds` -> `TicketService.get_statistics_services` -> `TicketDao.get_ticket_statistics`
- 追加：模块筛选改为未选择项目时展示全部有效模块，选择项目后展示所选项目下模块；工单列表页同步使用该筛选规则。
- 总共涉及页面：8

## [2026-06-21] INGEST-CODE | 工单主动拉取与多维配置统一
- 触发：用户要求根据桌面需求文档实现“工单主动拉取与配置优化”，包括外部字段模型、飞书多维表格主动拉取、字段映射和公共多维配置继承。
- 架构层：工单域 / 飞书多维表格集成 / 任务调度 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-21-ticket-bitable-pull-and-config-unify.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`bitableCommon/externalFieldModel/bitablePull` 配置 -> `TicketSyncService.run_bitable_pull_services` -> `TicketSyncNotifyService.query_bitable_records` -> `TicketSyncService.sync_external_ticket`
- 追加：主动拉取复用外部同步主链路，但会按 `recordId + snapshotHash` 判断记录是否变化；未变化时跳过，避免周期任务反复递增同步 revision。
- 总共涉及页面：9

## [2026-06-18] INGEST-CODE | 工单 AI Agent 已登记 worktree 分支复用
- 触发：用户反馈工单 AI 分析创建 `wemn_vender_master_1.3.8.41` 分支 worktree 时，目标目录不存在但 Git 提示该分支已被旧工作区路径占用。
- 架构层：工单域 / client_new Agent / Git worktree
- 创建的页面：`web/public/docs/2026-06-18-ticket-ai-worktree-registered-branch-reuse.md`
- 更新的页面：`client_new/services/ticket_ai_analysis_service.py`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`_ensure_local_worktree_repo` / `_ensure_worktree_repo` -> `_find_registered_worktree_by_branch` -> 复用 Git 已登记且分支校验通过的 worktree
- 总共涉及页面：4

## [2026-06-18] INGEST-CODE | 工单列表处理状态与评论按需加载
- 触发：用户要求工单列表“日志拉取”列改为“处理状态”并补充日志拉取中状态，详情页描述/翻译可收起，评论从历史页移到同级且点击后再异步请求。
- 架构层：工单域 / Web 控制台 / 评论接口 / 日志拉取状态筛选
- 创建的页面：`web/public/docs/2026-06-18-ticket-list-process-status-and-comments-lazy.md`
- 更新的页面：`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`web/src/api/ticket/ticket.js`、`web/src/views/ticket/constants.js`、`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/enums/ticket-enums.md`、`flows/ticket-automation-flow.md`
- 创建的双向链接：0 对
- 变更传播链：`TicketDao.list_comments` -> `GET /ticket/{ticket_id}/comments` -> 工单详情评论 tab 按需加载；`ticketProcessStatusOptions` -> `_build_ticket_process_status_filter` -> 工单列表处理状态筛选
- 总共涉及页面：10

## [2026-06-17] INGEST-CODE | 按人催办定时任务支持飞书参数覆盖
- 触发：用户要求按人催办通知的飞书筛选条件、人员字段名、时间字段名、视图、tableId、appToken 可在定时任务中配置；任务未配置时回退原参数配置。
- 架构层：工单域 / 飞书通知 / 任务调度
- 创建的页面：`web/public/docs/2026-06-17-ticket-person-reminder-task-override.md`
- 更新的页面：`server/module_task/scheduler_maintenance.py`、`server/modules/ticket/service/ticket_sync_service.py`、`server/modules/ticket/service/ticket_sync_notify_service.py`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`scheduler_maintenance.ticket_person_overdue_reminder` -> `TicketSyncService.run_person_reminder_services` -> `TicketSyncNotifyService.query_bitable_records`
- 总共涉及页面：6

## [2026-06-17] INGEST-CODE | 工单分类 AI 配置统一
- 触发：用户反馈工单分类统计配置分散在工单同步配置和 AI 配置中心，要求统一 Provider/提示词管理，并避免修改配置影响现有业务。
- 架构层：工单域 / 同步自动化 / AI Provider / AI 提示词模板 / 分类统计
- 创建的页面：`web/public/docs/2026-06-17-ticket-classification-config-unification.md`
- 更新的页面：`server/module_admin/service/ai_prompt_template_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/src/views/system/aiconfig/index.vue`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：AI 提示词默认模板 -> `ticket.sync.automation.aiClassification` 场景开关与选择项 -> `TicketLightAiService.classify_ticket_statistics` -> 工单分类统计字段回填
- 兼容策略：历史 `aiClassification.promptContent` 保存时保留，只作为旧配置兜底；新页面不再提供正文编辑入口。

## [2026-06-17] INGEST-CODE | 摄入工单自动归类排障日志增强
- 触发：用户反馈工单同步配置中点击统计未归类调用 `/sync/auto-category/stats` 没有自动归类，需要知道为什么没执行、正在执行什么、正在处理什么数据
- 架构层：工单域 / 同步自动化 / 轻量 AI 分类统计
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/2026-06-17-ticket-auto-category-debug-logs.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/service/ticket_light_ai_service.py` / `web/src/views/ticket/syncAutomation/index.vue` -> 工单同步自动归类排障
- 总共涉及页面：4

## [2026-06-17] INGEST-CODE | 工单相似度检索 Qdrant Provider
- 触发：用户反馈相似工单统计不准确，要求按标题和描述智能判断，并将向量库接入做成可配置方式。
- 架构层：工单域 / 相似工单检索 / Embedding / Qdrant / 批量重建任务
- 创建的页面：`web/public/docs/2026-06-17-ticket-similarity-qdrant-provider.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`flows/ticket-automation-flow.md`、`log.md`
- 变更传播链：`TicketEmbeddingService` -> `ticket.similarity.config` Provider 配置 -> `GET /ticket/similarity/config` / `POST /ticket/similarity/rebuild` -> 工单详情、协同追问、AI 分析上下文复用相似工单结果
- 追加：新增 `PUT /ticket/similarity/config`、菜单 `ticket.similarity.config` 和页面 `ticket/similarityConfig/index`；`sceneTriggers` 控制外部同步、远端拉取、手动新增、手动编辑、Excel 导入、关闭知识沉淀六类自动向量刷新场景。

## [2026-06-17] INGEST-CODE | 工单 AI Agent 分支 worktree 隔离
- 触发：用户反馈同一 Agent 并发分析不同工单时可能需要不同分支，并要求不影响原代码；未配置 localRepoPath 时自动创建目录并 checkout。
- 架构层：工单域 / client_new Agent / Codex Worker / Git worktree
- 创建的页面：`web/public/docs/2026-06-17-ticket-ai-agent-worktree-branch-isolation.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` -> 仓库映射 localRepoPath 分支校验、缺省 worktree 创建、Worker 提示词和阶段事件记录实际代码目录
- 追加：当历史映射携带 `localRepoPath` 但该目录当前分支与 `branchName` 不一致时，Agent 会记录原因并优先基于该本地仓库创建分支固定 worktree，复用原项目 Git 配置和凭据；只有无法自动创建 worktree 时才失败。

## [2026-06-16] INGEST-CODE | 工单保存接口非阻塞与按钮防重复提交
- 触发：用户反馈工单编辑弹窗保存响应慢，接口响应前保存按钮仍可重复点击，并要求接口异步化避免阻塞其他接口。
- 架构层：工单域 / Web 控制台 / FastAPI 事件循环 / 工单新增编辑保存链路
- 创建的页面：`web/public/docs/2026-06-16-ticket-save-nonblocking-submit-lock.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` -> 新增编辑保存线程池调度与弹窗提交态说明

## [2026-06-16] INGEST-CODE | 工单多维表格邮箱同步幂等优化
- 触发：用户要求外部推单入库时，如果多维表格邮箱之前已经成功同步过则不要每次重复同步，并确认推送和拉取是否都由配置控制。
- 架构层：工单域 / 外部同步链路 / 多维表格邮箱补齐 / 内网远端拉取
- 创建的页面：`web/public/docs/2026-06-16-ticket-bitable-email-sync-idempotent.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/tests/test_ticket_sync_mapping_boundary.py` -> 多维邮箱同步成功标记与推拉配置边界说明

## [2026-06-16] INGEST-CODE | 日志下载与工单同步接口非阻塞修复
- 触发：用户反馈日志拉取列表点击归档地址、原始压缩包和重新下载会导致 FastAPI 服务卡住，并要求检查外部推送、内网拉取等高频工单接口。
- 架构层：工单域 / 日志拉取 / 外部同步链路 / FastAPI 事件循环
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-download-nonblocking.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` -> 浏览器直链下载与同步服务线程池边界说明

## [2026-06-16] INGEST-CODE | 工单详情顶部描述布局优化
- 触发：用户反馈工单详情弹窗顶部详情表格中描述过长会撑变形，灰色关键字列换行会抬高短信息行；随后要求描述自动展示全部内容，并将原文和翻译分开展示、支持手动翻译。
- 架构层：工单域 / Web 控制台 / 工单详情弹窗 / 轻量 AI 翻译
- 创建的页面：`web/public/docs/2026-06-16-ticket-detail-summary-description-layout.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`ticket_controller.py` / `ticket_service.py` / `ticket.js` / `ticket/index.vue` -> 详情顶部基础信息表格、描述独立行和手动翻译入口

## [2026-06-16] INGEST-CODE | 工单 stepReason 排查过程评论同步
- 触发：用户要求将飞书 webhook 的 `stepReason` 大文本拆分为工单评论，并支持幂等、内网同步、本地评论不被覆盖和评论附件预留。
- 架构层：工单域 / 外部同步链路 / 评论模型 / 内网远端拉取
- 创建的页面：`web/public/docs/2026-06-16-ticket-step-reason-comment-sync.md`
- 创建的 SQL：`server/sql/20260616_ticket_comment_sync_source.sql`
- 更新的页面：`web/public/docs/update_history.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`ticket_controller.py` / `ticket_sync_service.py` / `ticket_service.py` / `ticket_dao.py` / `ticket_do.py` / `ticket_vo.py` -> stepReason 评论幂等同步说明

## [2026-06-16] INGEST-CODE | 工单同步重启恢复与远端拉取重试修复
- 触发：用户反馈服务重新部署/异常重启后同步状态可能不对，远端推送可更新但内部拉取后内部数据未更新。
- 架构层：工单域 / 外部同步链路 / 内网远端拉取 / 发布状态恢复
- 创建的页面：`web/public/docs/2026-06-16-ticket-sync-restart-retry-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/ticket-sync-automation.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/dao/ticket_dao.py` -> 工单同步发布状态、pending 租约与远端拉取重试说明

## [2026-06-16] INGEST-CODE | 日志拉取下载来源与 POS 列表区分
- 触发：用户要求日志拉取管理页下载优先本服务文件、缺失再走原始路径；工单详情页归档地址与原始压缩包分别下载；详情列表增加商家、门店、POSID。
- 架构层：工单域 / 日志拉取 / 下载来源 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-download-source-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`ticket_log_pull_service.py` / `ticket_controller.py` / `ticket.js` / `ticket/index.vue` / `logPullRecord/index.vue` -> 下载来源参数与详情页日志拉取列表展示

## [2026-06-16] INGEST-CODE | 日志拉取弹窗布局与通知修复
- 触发：用户要求日志拉取弹窗商家/门店/POSID 自动铺满整行，按数据类型切换 `modifyTime/path`，时间方式仅切割日志时显示，默认本地保存，并修复通知配置不生效。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 推送通知
- 创建的页面：`web/public/docs/2026-06-16-ticket-log-pull-dialog-layout-notify-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 变更传播链：`LogPullConfigFields.vue` / `LogPullNotifyConfigFields.vue` / `ticket_log_pull_service.py` -> 日志拉取提交参数清洗与结果通知

## [2026-06-16] INGEST-CODE | 工单编辑历史模块与人员名称保留
- 触发：用户反馈编辑页所属模块与当前项目模块不匹配时应原样显示/保存；1线人员和内部负责人不应重复显示 ID 选择与名称输入，无法匹配用户时应保留原始名称。
- 架构层：工单列表 / 工单编辑表单 / 工单关系字段解析
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`web/src/views/ticket/index.vue` / `UserSelect.vue` / `ticket_service.py` -> 历史模块文本保留 / 人员名称单控件回显与保存

## [2026-06-16] INGEST-CODE | 工单编辑模块回填与工单类型展示修复
- 触发：用户反馈工单列表中编辑保存后模块显示为空，且工单类型编辑前显示像所属模块、编辑后才正确。
- 架构层：工单列表 / 工单编辑表单 / 分类统计字段展示
- 更新的页面：`web/public/docs/update_history.md`、`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`web/src/views/ticket/index.vue` -> 编辑回填模块保护 / 提交前模块名称补齐 / 工单类型不回退旧分类

## [2026-06-16] INGEST-CODE | 工单分类统计独立字段与可视化枚举配置
- 触发：用户要求按 `D:\xj\Documents\工单分类统计设计.txt` 实现工单分类统计拆维，并将统计状态/枚举设计为可配置且可视化配置。
- 架构层：工单域 / 工单统计 / 同步自动化配置 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-16-ticket-classification-statistics-fields.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`log.md`
- 变更传播链：`ticket.sync.automation.statClassification` -> 工单表独立统计字段 -> 工单列表/流转/RCA/统计页展示

## [2026-06-15] INGEST-CODE | 远端拉取状态与内部负责人映射修复
- 触发：用户反馈内网拉取公网工单后状态仍显示公网原始文案，且公网有内部负责人但内网缺失。
- 架构层：工单域 / 外部同步链路 / 远端拉取入库
- 创建的页面：`web/public/docs/2026-06-15-ticket-remote-pull-status-owner-mapping.md`
- 更新的页面：`web/public/docs/update_history.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` -> 远端拉取状态与内部负责人映射说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 工单协同追问触发 AI 修复
- 触发：用户反馈工单详情页 `协同/AI` 中追问有保存输入内容，但没有发起 AI 分析
- 架构层：工单域 / AI Worker 编排 / 前端详情页
- 创建的页面：`web/public/docs/2026-06-15-ticket-message-run-ai-trigger-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `web/src/views/ticket/index.vue` -> 工单协同追问触发 AI 说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 工单 AI 整包日志摘要优化
- 触发：用户询问几十 MB 日志是否完整给 AI 分析，担心 token 消耗过高。
- 架构层：client_new Agent / 工单 AI 分析 / 日志整包处理
- 创建的页面：`web/public/docs/2026-06-15-ticket-ai-log-digest-optimization.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单 AI 日志整包摘要说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | Agent Codex CLI 执行链路修复
- 触发：用户反馈 Windows Agent 安装 Codex 桌面应用后，工单 AI 分析误用桌面应用 `codex.exe`、弹出 cmd 窗口，且账号并发限制错误被业务日志污染。
- 架构层：client_new Agent / 工单 AI 分析 / Codex CLI 执行
- 创建的页面：`web/public/docs/2026-06-15-agent-codex-cli-runtime-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/model/config.py` -> Agent Codex CLI 执行修复说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | 日志拉取重新拉取参数恢复兼容
- 触发：用户反馈工单详情页日志拉取记录点击“重新拉取”时报“当前记录缺少可重新拉取的原始参数”。
- 架构层：工单域 / 日志拉取 / 历史记录兼容
- 创建的页面：`web/public/docs/2026-06-15-ticket-log-pull-retry-payload-fallback.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 重新拉取参数恢复说明
- 总共涉及页面：4

## [2026-06-15] INGEST-CODE | API Key 使用审计非阻断处理
- 触发：用户反馈远端推单偶发 MySQL 2013，堆栈显示失败点为 API Key 鉴权阶段更新 `sys_api_key.last_used_ip/last_used_time`。
- 架构层：认证鉴权 / API Key / 工单外部同步入口
- 创建的页面：`web/public/docs/2026-06-15-api-key-usage-audit-nonblocking.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_admin/service/api_key_service.py` -> API Key 使用审计非阻断说明
- 总共涉及页面：3

## [2026-06-15] INGEST-CODE | 工单动态工作流状态与远端模块同步修复
- 触发：用户反馈远端推送 `ticketModle` 变化未正确更新，以及工作流新增/修改状态后工单流转无法选择新增状态。
- 架构层：工单域 / 外部同步链路 / 工作流流转 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-15-ticket-workflow-dynamic-status-and-remote-module.md`
- 更新的页面：`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`flows/ticket-workflow-routing.md`、`flows/ticket-external-sync-flow.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `web/src/views/ticket/index.vue` -> 工单动态状态与远端模块同步文档
- 总共涉及页面：6

## [2026-06-15] INGEST-CODE | 新增专题工单会话状态统计定时任务
- 触发：用户要求根据 `D:\xj\Downloads\topic_ticket_stats.py` 将内部逻辑实现在当前项目的定时任务中，并通过任务参数配置所需信息。
- 架构层：工单域 / 任务调度 / 飞书群消息统计
- 创建的页面：`web/public/docs/2026-06-15-ticket-topic-stats-scheduler.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_topic_stats_service.py` / `server/module_task/scheduler_maintenance.py` -> 专题统计定时任务文档
- 总共涉及页面：3

## [2026-06-12] INGEST-CODE | 工单群消息@人补强（模板别名 + 人员对象邮箱解析）
- 触发：用户要求外部推单/远端拉取发群时，按模板决定是否 @ 报告人与当前责任人，并通过邮箱查询飞书 `open_id` 稳定 @ 人。
- 架构层：工单域 / 外部同步链路 / 飞书通知
- 创建的页面：`web/public/docs/2026-06-12-ticket-group-mention-template-and-person-email-compat.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_notify_service.py` -> 工单通知链路文档
- 总共涉及页面：3

## [2026-06-12] INGEST-CODE | 自动群推送状态条件改为可视化配置
- 触发：用户要求将自动群推送的状态判断从后端写死逻辑改为可视化配置，并确认外部推单/远端拉取都生效且不影响手动推送。
- 架构层：工单域 / 同步自动化配置 / 群消息通知
- 创建的页面：`web/public/docs/2026-06-12-ticket-group-auto-push-status-condition-config.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `web/src/views/ticket/syncAutomation/index.vue` -> 工单同步配置文档
- 总共涉及页面：4

## [2026-06-11] INGEST-CODE | 修复外部推单秒级重复导致群消息重复发送
- 触发：用户反馈外部同工单短时间重复推送时，群消息仍会重复发送，要求“收到后立即判重”。
- 架构层：工单域 / 外部同步链路 / 群消息通知
- 创建的页面：`web/public/docs/2026-06-11-ticket-external-rapid-duplicate-dedup-lock.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` -> 工单同步与群推送幂等文档
- 总共涉及页面：4

## [2026-06-11] INGEST-CODE | 修复按人催办过滤公式导致飞书参数异常
- 触发：用户反馈“按人催办通知”一旦填写过滤公式，调用飞书接口即报参数异常。
- 架构层：工单域 / 飞书通知 / 多维表格查询
- 创建的页面：`web/public/docs/2026-06-11-person-reminder-filter-formula-fix.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` -> 工单通知链路文档
- 总共涉及页面：3

## [2026-06-10] INGEST-CODE | AI配置中心默认提示词补齐（自动分类/日志参数提取）
- 触发：用户反馈 AI 配置中心“自动分类提示词、日志参数提取提示词”默认无法选择，要求系统默认插入可选模板，内容可为空以便后续填写。
- 架构层：系统管理 / AI配置中心 / 提示词模板
- 创建的页面：`web/public/docs/2026-06-10-ai-config-default-common-prompts.md`
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_admin/service/ai_prompt_template_service.py` / `server/module_admin/service/ai_config_service.py` -> AI配置中心文档
- 总共涉及页面：3

## [2026-06-10] INGEST-CODE | 工单通知补强（优先级分流 + 汇总统计 + 统一飞书凭证）
- 触发：用户提供“工单通知相关”需求，要求补齐优先级分流发群、按人催办、定时汇总统计、统一 app_id/app_secret 与配置可视化。
- 架构层：工单域 / 飞书通知 / 任务调度 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-10-ticket-notify-routing-and-summary.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/module_task/scheduler_maintenance.py` / `web/src/views/ticket/syncAutomation/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-10] INGEST-CODE | 修复日志拉取列表 modify_time 字段异常
- 触发：用户反馈工单列表页报错 `'TicketLogPullRecord' object has no attribute 'modify_time'`
- 架构层：工单域 / 日志拉取
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-10] INGEST-CODE | 修复日志拉取弹窗关联工单回填缺失
- 触发：用户反馈日志拉取弹窗中关联工单后，商家ID/门店/POS未自动回填。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-10] INGEST-CODE | 工单自动拉日志门槛 + 自动分类 + 日志弹窗回填
- 触发：用户要求自动拉日志必须参数齐全才执行，并新增工单自动分类能力（含批量重跑），同时增强日志拉取弹窗回填与“日志成功后版本号自动回填”。
- 架构层：工单域 / 外部同步链路 / 轻量 AI 配置中心 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-10-ticket-auto-logpull-and-auto-category.md`
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_light_ai_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/module_admin/service/ai_config_service.py` / `server/module_admin/entity/vo/ai_config_vo.py` / `web/src/views/system/aiconfig/index.vue` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/logPullRecord/index.vue` / `web/src/components/ticket/LogPullConfigFields.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-10] INGEST-CODE | 工单通知系统（群消息推送 + 按人催办）落地
- 触发：用户要求基于飞书多维表格按人催办、支持工单群消息推送、并将同步链路翻译开关收敛到清晰配置。
- 架构层：工单域 / 外部同步链路 / 飞书通知 / 任务调度 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_sync_notify_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/module_task/scheduler_maintenance.py` / `web/src/views/ticket/syncAutomation/index.vue` / `web/src/views/system/aiconfig/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-06-09] INGEST-CODE | 修复日志拉取弹窗门店联动不重新查询
- 触发：用户反馈在日志拉取弹窗中输入或选择商家后，门店下拉没有只显示对应商家的门店。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/api/ticket/ticket.js` / `web/src/components/ticket/LogPullConfigFields.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-06-09] INGEST-CODE | 修复门店配置列表分页数据读取层级错误
- 触发：用户反馈门店配置页面查询后后端已返回数据，但前端列表不显示。
- 架构层：工单域 / 日志拉取 / Web 控制台
- 创建的页面：无
- 更新的页面：`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/logPullRecord/index.vue` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-09] INGEST-CODE | 修复门店配置导入误去重与大文件导入卡顿
- 触发：用户反馈 `/ticket/log-pull/store-configs/import` 上传 3K 门店配置后只剩少量记录，同时导入期间影响其他服务可用性。
- 架构层：工单域 / 日志拉取 / 门店配置导入 / 知识库同步
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/dao/ticket_log_pull_dao.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-06-05] INGEST-CODE | 日志拉取新增门店配置导入与项目商家映射
- 触发：用户要求给日志拉取页面增加门店信息导入入口，支持增量/覆盖导入，并补充项目到商户编号的映射和链路日志。
- 架构层：工单域 / 日志拉取 / Web 控制台 / 知识库同步
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/entity/do/ticket_log_pull_do.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/dao/ticket_log_pull_dao.py` / `web/src/views/ticket/logPullRecord/index.vue` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-31] INGEST-CODE | 工单外部同步与内网拉取链路落地
- 触发：用户需要双环境部署下的工单同步能力，要求知道哪些数据已被某个内网系统拉取过，并在同步后自动识别归属信息、匹配类似工单、按条件串联日志拉取与 AI 分析，同时记录执行失败步骤。
- 架构层：工单域 / 外部系统集成 / 自动化链路 / 系统参数配置
- 创建的页面：`flows/ticket-external-sync-flow.md`
- 更新的页面：`entities/services/ticket-domain.md`、`index.md`、`log.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 创建的双向链接：2 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/entity/vo/ticket_vo.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/perms.py` -> `wiki/flows/ticket-external-sync-flow.md` -> `wiki/entities/services/ticket-domain.md`
- 总共涉及页面：6

## [2026-05-31] INGEST-CODE | 日志拉取页面商家门店改为参数配置联动下拉
- 触发：用户要求日志拉取页面的商家、门店改为可配置并沿用现有服务端参数配置，且商家与门店联动。
- 架构层：工单域 / 日志拉取 / 系统参数配置 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`web/public/docs/ticket-log-pull-design.md`、`web/public/docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `web/src/api/ticket/ticket.js` / `web/src/views/ticket/logPullRecord/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-29] INGEST-CODE | 定时任务新增线程/进程执行方式并拆分 Worker
- 触发：用户要求按任务配置选择线程或进程执行，并落地长期稳定方案，去掉业务层二级 spawn 子进程
- 架构层：任务调度域 / Celery Worker / 任务执行模型
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_job_models.py` / `server/module_task/celery_job_service.py` / `server/config/get_db.py` / `server/supervisord.conf` / `web/src/views/monitor/job/index.vue` / `web/src/views/qtr/job/index.vue` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 临时统一 Celery 任务为线程内直执行
- 触发：用户要求先排除 Linux 下业务子进程 `spawn` 与 IPC 干扰，确认任务逻辑在线程直执行模式下是否正常
- 架构层：任务调度域 / Celery Worker / 任务执行模型
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 修复 Windows 下 Celery 业务子进程导入失败
- 触发：用户在 Windows 开发环境执行定时任务时，Worker 已收到任务，但二级 `spawn` 子进程启动阶段报 `ModuleNotFoundError: No module named 'module_task'`
- 架构层：任务调度域 / Celery Worker / Windows 多进程导入路径
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-29] INGEST-CODE | 修复定时任务子进程结果回传竞态
- 触发：用户反馈定时任务执行记录显示“子进程未返回结果”，但应用日志里没有异常堆栈
- 架构层：任务调度域 / Celery Worker / 子进程 IPC
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` -> 任务调度域知识页
- 总共涉及页面：2

## [2026-05-29] INGEST-CODE | 落地 AI 分析提示词分层设计
- 触发：用户要求直接落地“AI 分析提示词分层设计方案”，希望项目/模块拥有默认提示词，且提交分析时允许额外说明
- 架构层：工单域 / AI 提示词组装 / 前端提交弹窗
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_prompt_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/service/ticket_service.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-28] INGEST-CODE | 调整工单 AI 仓库映射优先级到 Agent 本地配置
- 触发：用户指出工单 AI 仓库映射里的工作区根目录和本地仓库路径更像 Agent 本地配置，要求服务端改为非必填，并在 Agent 本地配置存在时始终以本地配置为准
- 架构层：工单域 / Agent 编排 / 新版客户端
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/ui/pages/agent_page.py` / `web/src/views/ticket/aiRepoMapping/index.vue` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-27] INGEST-CODE | 修复 Celery 任务长执行锁过期与失联状态恢复
- 触发：用户反馈 Celery Worker 异常后任务状态会一直停留在 running，且无法再次手动执行；另有 2 小时任务在 `lock_ttl_seconds=3600` 下执行到 1 小时后又被自动重复派发
- 架构层：任务调度域 / Redis 锁 / 运行态心跳 / 手动终止
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` / `server/module_task/celery_job_service.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-27] INGEST-CODE | 调整 Celery 执行日志为启动写入、结束回填
- 触发：用户怀疑存在其他触发途径，希望能在任务执行中直接看到是谁触发、何时进入 running；现有执行日志只在任务完成后写入，导致运行中缺少数据库记录
- 架构层：任务调度域 / 执行日志生命周期
- 创建的页面：无
- 更新的页面：`entities/services/task-scheduler-domain.md`、`entities/data-models/task-core-models.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_task/celery_tasks.py` / `server/module_task/celery_job_service.py` -> 任务调度域知识页
- 总共涉及页面：3

## [2026-05-26] INGEST-CODE | 修复工单 AI 分析 WebSocket loop 归属错误
- 触发：用户先反馈工单 AI 分析失败后重试时任务长期停留在“进行中”，修复后又暴露出发起分析时报 `got Future attached to a different loop`
- 架构层：工单域 / Agent 编排 / 异步事件循环
- 创建的页面：`docs/2026-05-26-ticket-ai-analysis-future-threadsafe-result.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/module_qtr/service/agent_service.py` / `server/module_qtr/controller/agent_controller.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-26] INGEST-CODE | 修复 AI 分析期间 Agent 事件循环被阻塞导致断连
- 触发：用户反馈启动 AI 分析时 Agent 经常断开，怀疑是大文件占用连接过久，要求在不改数据流前提下定位根因并采用稳定方案处理
- 架构层：工单域 / Agent 编排 / 新版客户端
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`flows/ticket-automation-flow.md`、`docs/ticket_system_phase1.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`client_new/services/ticket_ai_analysis_service.py` / `client_new/server/agent_server.py` / `server/module_qtr/controller/agent_controller.py` / `server/module_qtr/service/agent_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-20] INIT-CODE | 初始化 Wiki 基础结构
- 触发：用户执行 `$llm-wiki init`
- 架构层：知识库初始化
- 创建的页面：`overview.md`、`purpose.md`、`concepts/architecture-overview.md`、`entities/services/backend-application.md`、`entities/components/frontend-bootstrap.md`、`flows/http-api-entrypoint.md`、`schema.md`、`index.md`
- 更新的页面：无
- 创建的双向链接：13 对
- 变更传播链：`README.md`/`server/server.py`/`server/config/env.py`/`web/src/main.js` -> Wiki 总览与入口页
- 总共涉及页面：8

## [2026-05-20] INGEST-CODE | 摄入 client 与 client_new 模块
- 触发：用户要求摄入 `client/` 与 `client_new/` 模块
- 架构层：桌面客户端层
- 创建的页面：`concepts/desktop-client-architecture.md`、`entities/services/legacy-flet-client.md`、`entities/services/new-pyside-client.md`、`entities/components/legacy-client-bootstrap.md`、`entities/components/new-client-bootstrap.md`
- 更新的页面：`index.md`
- 创建的双向链接：10 对
- 变更传播链：`client/src/main.py`/`client/src/navigationMenu.py`/`client_new/main.py`/`client_new/ui/main_window.py` -> 客户端知识页
- 总共涉及页面：6

## [2026-05-20] INGEST-CODE | 摄入项目其余模块知识库
- 触发：用户要求完成项目中所有模块知识库创建
- 架构层：后端平台 / Web 控制台 / 旧版客户端 / 新版客户端
- 创建的页面：`concepts/module-landscape.md`、`entities/components/server-infrastructure.md`、`entities/services/admin-domain.md`、`entities/services/hrm-domain.md`、`entities/services/qtr-domain.md`、`entities/services/task-scheduler-domain.md`、`entities/services/ticket-domain.md`、`entities/components/web-shell.md`、`entities/services/web-feature-domains.md`、`entities/components/legacy-client-shell.md`、`entities/components/legacy-client-runtime.md`、`entities/services/legacy-client-features.md`、`entities/components/new-client-shell.md`、`entities/components/new-client-runtime.md`、`entities/services/new-client-services.md`、`entities/data-models/admin-core-models.md`、`entities/data-models/hrm-core-models.md`、`entities/data-models/task-core-models.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/hrm-enums.md`、`entities/enums/ticket-enums.md`
- 更新的页面：`index.md`、`overview.md`、`purpose.md`
- 创建的双向链接：28 对
- 变更传播链：`server/` / `web/src/` / `client/src/` / `client_new/` -> 模块全景图与各域页面
- 总共涉及页面：24

## [2026-05-20] INGEST-CODE | 摄入工单项目/参数配置/流转路由改造
- 触发：用户要求将日志拉取地址与 Cookie 迁移到参数配置、工单归属改为测试项目/模块、状态流转支持默认处理人与通知预留
- 架构层：工单域 / HRM 测试管理域 / 系统参数配置
- 创建的页面：`flows/ticket-workflow-routing.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`index.md`
- 创建的双向链接：7 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/workflow/index.vue` -> 工单域知识页与流转流程页
- 总共涉及页面：5

## [2026-05-20] INGEST-CODE | 摄入工单日志弹窗与时间范围收紧改造
- 触发：用户要求将日志展示改为弹窗，日志时间范围必填，并且只读取 `*_pos.log*` 日志
- 架构层：工单域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：1

## [2026-05-21] INGEST-CODE | 摄入工单日志实时重截查看改造
- 触发：用户要求在日志弹窗里默认查看入库内容，仅在查看原始文档时联动显示本次截取范围并支持按调整后的时间实时重截查看
- 架构层：工单域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/controller/ticket_controller.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：1

## [2026-05-21] INGEST-CODE | 摄入工单日志提交弹窗与提示按钮改造
- 触发：用户要求把日志拉取提交区域改为弹窗，参数配置入口改为通用提示按钮，日志页只保留记录列表
- 架构层：工单域 / Web 控制台 / 通用组件
- 创建的页面：`docs/2026-05-21-ticket-log-submit-dialog-prompt-button.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/components/PromptButton/index.vue` / `web/src/views/ticket/index.vue` / `web/src/main.js` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 摄入工单项目选项状态修复与公共项目管理说明
- 触发：用户反馈新增工单时项目/模块下拉为空，需要确认是否复用公共项目管理
- 架构层：工单域 / HRM 测试管理域
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-20-ticket-param-config-workflow-change.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_import_service.py` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-21] INGEST-CODE | 摄入工单事件JSON安全序列化修复
- 触发：用户在按时间点提交日志时，工单事件写入因包含 datetime 导致 JSON 序列化失败
- 架构层：工单域
- 创建的页面：`docs/2026-05-21-ticket-event-data-json-safe.md`
- 更新的页面：`entities/services/ticket-domain.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 修复日志拉取事件写入绕过 JSON 安全转换的问题
- 触发：用户反馈提交日志拉取任务仍然因 datetime 进入 event_data 而报错
- 架构层：工单域
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-21-ticket-event-data-json-safe.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-21] INGEST-CODE | 摄入日志按时间范围完整入库与换行开关改造
- 触发：用户要求日志按时间范围完整入库，不要静默截断，并支持默认不换行查看
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-event-data-json-safe.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `web/src/views/ticket/index.vue` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-21] INGEST-CODE | 摄入工单日志前端解压展示改造
- 触发：用户说明后端仅返回压缩结果，要求前端在显示时自行解压
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-log-content-decompress.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-21] INGEST-CODE | 摄入工单日志记录级重拉重下重截改造
- 触发：用户要求在日志拉取列表和详情页增加重新拉取、重新下载、重新截取功能
- 架构层：工单域 / Web 控制台
- 创建的页面：`docs/2026-05-21-ticket-log-retry-redownload-reextract.md`
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：4

## [2026-05-22] INGEST-CODE | 摄入工单AI分析任务与仓库映射能力
- 触发：用户要求根据最终方案实现工单自动分析、调用 Codex Worker 回写结果，并增加版本/仓库/分支映射管理
- 架构层：工单域 / AI Worker 编排 / Web 控制台
- 创建的页面：`docs/2026-05-22-ticket-ai-analysis-final-solution.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`entities/enums/ticket-enums.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/dao/ticket_ai_dao.py` / `server/modules/ticket/controller/ticket_controller.py` / `web/src/views/ticket/index.vue` / `web/src/api/ticket/ticket.js` -> 工单域知识页
- 总共涉及页面：5

## [2026-05-22] INGEST-CODE | 摄入工单表单与 AI 流程联动调整
- 触发：用户要求修复 TicketStatusHistory 序列化报错，并将工单号、版本号、仓库映射菜单和项目/模块联动纳入最终业务流程
- 架构层：工单域 / AI Worker 编排 / Web 控制台
- 创建的页面：`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `web/src/views/ticket/index.vue` / `web/src/views/ticket/ai-repo-mapping/index.vue` -> 工单域知识页
- 总共涉及页面：5

## [2026-05-22] INGEST-CODE | 修复工单分析序列化与模块/路由联动兜底
- 触发：用户反馈提交分析仍报 `TicketStatusHistory` 序列化错误，且模块列表为空、AI 仓库映射路由需要改为驼峰路径
- 架构层：工单域 / HRM 测试管理域 / Web 控制台
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` / `server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/modules/ticket/perms.py` / `web/src/router/index.js` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI分析阶段日志与失败原因回写
- 触发：用户要求 AI 分析失败时能在系统日志里看到具体执行到哪一步、哪一步失败以及异常堆栈，数据库仅保留最后失败原因
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-06-16] INGEST-CODE | 修复工单 pending 候选窗口导致内网拉取为空
- 触发：用户反馈 2026-06-16 上午 10 点后公网能接收推送，但内网拉不到新增数据
- 架构层：工单域 / 外部同步 / 内网远端拉取
- 创建的页面：无
- 更新的页面：`docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/dao/ticket_dao.py` -> 工单外部同步与内网拉取流程
- 总共涉及页面：2

## [2026-06-21] INGEST-CODE | 工单模块 code 筛选与项目内唯一
- 触发：用户要求工单列表和工单统计增加按模块 code 搜索，模块 code 改为项目下唯一，并且筛选下拉枚举动态从后端获取。
- 架构层：工单域 / HRM 模块管理 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-21-ticket-module-code-filter-and-project-unique.md`
- 更新的页面：`server/modules/ticket/entity/vo/ticket_vo.py`、`server/modules/ticket/controller/ticket_controller.py`、`server/modules/ticket/service/ticket_service.py`、`server/modules/ticket/dao/ticket_dao.py`、`server/module_hrm/service/module_service.py`、`web/src/views/ticket/index.vue`、`web/src/views/ticket/statistics/index.vue`、`web/src/views/hrm/module/index.vue`、`web/public/docs/update_history.md`、`entities/services/ticket-domain.md`、`log.md`
- 变更传播链：`/ticket/modules/options` 返回 `moduleCode` -> 工单列表/统计页动态生成模块 code 下拉 -> `/ticket/list` 与 `/ticket/statistics/overview` 增加 `moduleCode/moduleCodes` 过滤；`module_service.py` -> HRM 模块 code 唯一性改为项目内校验

## [2026-05-22] INGEST-CODE | 修复 Windows 下 codex Worker 路径解析问题
- 触发：用户在 Windows 开发环境提交 AI 分析时，日志显示 `WinError 2`，服务进程找不到 `codex` 可执行文件
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 独立 CODEX_HOME 兜底
- 触发：用户继续反馈 AI 分析在 Windows 下因 Codex app-server 初始化和临时目录状态导致失败
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker .env 优先加载规则
- 触发：用户要求 AI 分析优先读取 Codex 配置目录中的 `.env`，再回退到系统环境变量
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 排障日志增强
- 触发：用户继续排查 Windows 下 AI Worker 返回 `invalid_request_error`，需要对比终端与后台线程的运行差异
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Worker 输出 schema 约束修复
- 触发：用户提供最新 stderr，确认 Codex 返回 `Invalid schema for response_format 'codex_output_schema'`
- 架构层：工单域 / AI Worker 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` -> 工单域知识页
- 总共涉及页面：2

## [2026-05-22] INGEST-CODE | 摄入工单AI Agent 远程执行链路
- 触发：用户确认短期方案改为本地启动 agent，由服务端通过 WebSocket 调 agent 调用 Codex 并回传结果
- 架构层：工单域 / Agent 编排
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`、`web/public/docs/ticket_system_phase1.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_ai_analysis_service.py` / `server/module_qtr/service/agent_service.py` / `server/module_qtr/controller/agent_controller.py` / `client_new/services/ticket_ai_analysis_service.py` / `client_new/server/agent_server.py` -> 工单域知识页
- 总共涉及页面：3

## [2026-05-22] INGEST-CODE | 摄入工单自动拉日志与自动AI联动
- 触发：用户要求新增工单时可同时配置是否拉日志、日志成功后是否自动AI，以及在日志拉取页补充自动AI Agent 选择
- 架构层：工单域 / 日志拉取 / Agent 编排 / 前端按需加载
- 创建的页面：`flows/ticket-automation-flow.md`
- 更新的页面：`entities/services/ticket-domain.md`、`entities/data-models/ticket-core-models.md`、`docs/2026-05-22-ticket-form-and-ai-flow-update.md`、`wiki/index.md`
- 创建的双向链接：1 对
- 变更传播链：`server/modules/ticket/service/ticket_service.py` / `server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/service/ticket_ai_analysis_service.py` / `web/src/views/ticket/index.vue` -> 工单自动化链路流程
- 总共涉及页面：5

## [2026-06-09] INGEST-CODE | 摄入日志拉取门店下拉的 org_no 语义
- 触发：用户反馈日志拉取弹窗里的门店下拉不友好，需要支持按 `org_no`、`sap_org_no` 和门店名称搜索，并且实际提交值应使用 `org_no`
- 架构层：工单域 / 日志拉取 / 前端联动选择
- 创建的页面：无
- 更新的页面：`entities/services/ticket-domain.md`、`docs/ticket-log-pull-design.md`、`docs/update_history.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_log_pull_service.py` / `server/modules/ticket/entity/vo/ticket_log_pull_vo.py` / `server/modules/ticket/entity/do/ticket_log_pull_do.py` / `web/src/components/ticket/LogPullConfigFields.vue` / `web/src/views/ticket/index.vue` -> 工单域知识页
- 总共涉及页面：5

## [2026-06-10] INGEST-CODE | 摄入工单同步“统一提取 + 半合并AI调用”链路
- 触发：用户要求将工单同步中的标题总结、分类整理、日志参数提取尽量合并为一次轻量 AI 调用，翻译保留独立调用；并新增日志参数提取配置能力
- 架构层：工单域 / 轻量AI配置中心 / 同步自动化
- 创建的页面：无
- 更新的页面：`docs/update_history.md`、`log.md`
- 创建的双向链接：0 对
- 变更传播链：`server/modules/ticket/service/ticket_light_ai_service.py` / `server/modules/ticket/service/ticket_sync_service.py` / `server/module_admin/service/ai_config_service.py` / `server/module_admin/entity/vo/ai_config_vo.py` / `web/src/views/system/aiconfig/index.vue` -> 工单域知识页
- 总共涉及页面：5
## [2026-06-24] INGEST-DOC | 多维表格过滤条件 JSON 文案修正
- 触发：用户确认多维表格查询条件配置已经改为 JSON，但页面和文档仍提示填写公式文本；随后要求主动拉取默认按更新时间或创建时间最近 1 小时在飞书请求参数中过滤，不能先全量拉取后本地过滤。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-filter-json-doc-fix.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_notify_service.py`、`server/modules/ticket/service/ticket_sync_service.py`、`web/src/views/ticket/syncAutomation/index.vue`、`web/public/docs/2026-06-21-ticket-bitable-pull-and-config-unify.md`、`web/public/docs/ticket-sync-automation.md`、`web/public/docs/update_history.md`
- 变更传播链：`ticket.sync.automation.*.filterFormula` 文案 -> 飞书 `records/search` filter JSON 配置提示 -> 后端错误提示；`createdAfter/updatedAtField/fieldMappings.createTime` -> 主动拉取云端时间窗口 filter；`externalSyncRequiredFields` -> 多维主动拉取记录级必填校验。

## [2026-06-24] INGEST-CODE | 工单 AI 分析弹窗默认值与提交体验修正
- 触发：用户要求发起 AI 分析时自动填入 Provider、Agent、追加提示词，日志模式默认摘要 + 完整目录，并排查 2026-06-23 改动导致提交后弹窗不关闭且继续 loading 的等待点。
- 架构层：工单域 / AI 分析 / Web 控制台
- 创建的页面：`web/public/docs/2026-06-24-ticket-ai-analysis-dialog-defaults.md`
- 更新的页面：`web/src/views/ticket/index.vue`、`web/public/docs/update_history.md`
- 变更传播链：AI 分析弹窗默认值 -> Provider 绑定 Agent 前端联动 -> 提交成功立即关闭弹窗 -> 后台短轮询保留快速失败提示。

## [2026-06-24] INGEST-CODE | 多维表格主动拉取嵌套时间过滤修复
- 触发：用户反馈 `TicketSyncService._build_bitable_pull_time_filters` 支持嵌套 filter 后，内部时间字段值无法替换；期望嵌套模式在最外层 `children` 追加时间范围，同时递归补齐内部时间字段值，扁平模式只补齐已有字段。
- 架构层：工单域 / 飞书多维表格集成 / 同步自动化配置
- 创建的页面：`web/public/docs/2026-06-24-ticket-bitable-nested-time-filter.md`
- 更新的页面：`server/modules/ticket/service/ticket_sync_service.py`、`server/tests/test_ticket_sync_mapping_boundary.py`、`web/public/docs/2026-06-22-ticket-bitable-pull-created-after.md`、`web/public/docs/update_history.md`、`wiki/entities/services/ticket-domain.md`、`wiki/flows/ticket-external-sync-flow.md`
- 变更传播链：`bitablePull.filterFormula` 嵌套 filter -> `_fill_dynamic_time_filter_values` 递归补值 -> `_build_bitable_pull_time_filters` 顶层 children 追加默认时间窗口 -> 飞书 `records/search` 请求过滤。
## [2026-06-24] code | 工单用户配置、列表列与统计块显示
- 更新页面：web/src/views/ticket/index.vue, web/src/views/ticket/statistics/index.vue
- 新增后端：module_admin 用户配置模型、DAO、Service、Controller
- 文档：web/public/docs/2026-06-24-ticket-user-config-columns-stat-blocks.md
