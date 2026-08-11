---
title: 工单外部同步与内网拉取流程
type: flow
source_type: code
entry_points:
  - type: http
    method: POST
    path: /ticket/sync/external
    trigger: 外部工单系统推送工单，或内网系统将拉取到的工单再次入站
  - type: http
    method: GET
    path: /ticket/sync/pending
    trigger: 内网消费方按 consumer 拉取当前未交付版本的工单
  - type: http
    method: POST
    path: /ticket/sync/ack
    trigger: 消费方可选回写处理结果
  - type: background
    method: lark_oapi.ws
    path: im.message.receive_v1
    trigger: 飞书官方 SDK 长连接接收群消息事件
created: 2026-05-31
updated: 2026-07-27
---

# 工单外部同步与内网拉取流程

该流程描述双环境部署下的工单同步链路：公网环境可作为外部工单入口，内网环境按消费方拉取未交付版本；是否已经被拉取不再依赖单一布尔值，而是按工单版本和消费方分别跟踪。

2026-07-31 起，字段识别后、入库 payload 构建前会读取外部接口字段执行工单类型映射。规则命中写入类型、规则 ID 和审计元数据；人工分类不覆盖，未命中才允许后续 AI 分类。

```mermaid
sequenceDiagram
  participant E as 外部工单系统
  participant G as 同步接口
  participant S as 工单同步服务
  participant DS as 同步交付服务
  participant D as 工单与同步元数据
  participant I as 内网消费系统
  participant A as 自动化链路

  E->>G: POST /ticket/sync/external
  G->>S: 按 ticketNo 创建或更新工单
  S->>D: 写入 external_sync.revision 与来源信息
  S->>A: 按配置执行识别/相似工单/日志/AI
  I->>G: GET /ticket/sync/pending?consumer=inner-system
  G->>DS: 查询当前 consumer 未交付 revision
  DS->>D: 写入 pulled 租约、batch_id、last_pulled_at
  DS-->>I: 返回当前批次工单
  I->>G: POST /ticket/sync/ack
  G->>DS: 回写处理结果
  DS->>D: 成功回执推进 delivered_revision
```

## 入口信息

| 类型 | 方法 | 路径 | 触发条件 |
|---|---|---|---|
| http | POST | `/ticket/sync/external` | 外部系统推送工单，或内部系统把拉到的工单重新入站 |
| http | GET | `/ticket/sync/pending` | 内网消费方按 `consumer` 拉取当前未交付版本 |
| http | POST | `/ticket/sync/ack` | 内网消费方需要可选回写本批次处理结果 |

## 详细步骤

| 步骤 | 说明 |
|---|---|
| 1 | 外部系统调用 `POST /ticket/sync/external`，`TicketExternalSyncRequestService` 读取 JSON 或表单请求体并归一化字段；必填 `ticketNo`、`description`、`internalPriority`、`ticketVender`、`ticketModle`、`createTime`、`reporterName`，`title` 允许缺省。 |
| 2 | `TicketSyncService.sync_external_ticket` 以 `ticketNo` 为幂等键创建或更新工单，入库 payload 由 `TicketSyncPayloadService.build_upsert_payload` 构造，并在 `extra_data.external_sync` 中递增 `revision`。 |
| 3 | `TicketSyncPayloadService` 统一维护入库同步元数据：来源系统、来源记录 ID、远端 source revision、外部原始创建时间（`externalCreateTime`）、最近导入时间、自动化执行状态、项目/模块文本兜底和 `log_pull_hints`；消费者交付状态由 `TicketSyncDeliveryService` 更新。 |
| 4 | 主链路会先完成工单入库并快速返回；入库后先写 `publish_ready=false`、`publish_status=processing_ai`，AI翻译、AI标题总结、自动化与群推送由 `TicketSyncPostProcessService` 投递 Celery 或回退本地后台执行，避免阻塞 `POST /ticket/sync/external` 请求。 |
| 5 | 字段识别由 `TicketSyncAutomationService.detect_fields` 承接，采用可配置映射和正则规则：项目先按 `ticketVender` 命中 `projectMappings`，未命中再按 `projectCode` 业务码兜底；模块先按 `ticketModle` 命中 `moduleMappings`，未命中再按 `moduleCode` 业务码兜底；不按标题/描述全文匹配项目映射；商家按关键词包含匹配；处理人按完整名称匹配（支持 email）；门店按商家ID+`sap_org_no` 查询配置。项目或模块未匹配本地 HRM 配置时，会保留外部原始文本到工单项目/模块名称字段。已有工单再次同步时，只要本次外部数据携带项目或模块字段，就按本次解析结果覆盖旧归属；解析不到本地 ID 时清空旧 ID 并保留本次外部文本。规则统一存放在 `ticket.sync.automation`。 |
| 5.1 | 外部推送多维表格邮箱补齐由 `TicketExternalBitableEmailService` 承接，并由 `externalSyncBitable.enabled` 控制；同一工单已成功补齐过同一个 `recordId` 时，会根据 `extra_data.external_sync.bitableEmailSync` 跳过重复查询。 |
| 5.1.1 | 飞书多维表格相关配置已收敛到公共配置 `bitableCommon`；外部推送邮箱补齐、按人催办、汇总统计和主动拉取默认继承公共配置，局部配置非空时覆盖。 |
| 5.1.2 | 新增主动拉取链路 `bitablePull`：调度任务按条件查询飞书多维表格记录，由 `TicketBitablePullService` 经 `fieldMappings` 映射成外部同步字段后复用 `POST /ticket/sync/external` 入库；任务参数提供映射时优先于可视化配置；默认时间窗口在飞书 `records/search` filter 中按更新时间字段或创建时间字段大于等于当前时间前 1 小时执行，`createdAfter` 仅用于覆盖窗口下限；嵌套 filter 会在最外层 `children` 追加默认时间窗口并递归补齐内部时间字段空值，扁平 filter 只补齐已有时间字段；分页查询中 `page_size/page_token` 放在 URL 查询参数，`filter/view_id/view_type` 放在请求体，并对重复 `page_token` 熔断，避免飞书返回同一页导致循环拉取。 |
| 5.1.3 | 主动拉取会把 `recordId + snapshotHash` 记录到 `extra_data.bitable_pull`；同一记录内容未变化时跳过，避免周期任务反复制造新 revision。 |
| 5.1.4 | 飞书“查询记录”接口在当前环境中可能只返回 `record_id`；服务会继续按缺失记录的 `record_id` 调用 `records/batch_get(with_shared_url=true)` 批量补齐 `shared_url`，主动拉取和按人催办统一透传该真实详情地址，不再直接拼接页面 URL。 |
| 5.1.5 | 主动拉取配置页的字段预览优先读取飞书字段元数据，不使用运行时 `filterFormula/createdAfter`；字段元数据不可用时才回退到不带过滤条件的样例记录推断字段，避免最近时间窗口无记录导致字段下拉为空。 |
| 5.1.6 | 主动拉取定时任务没有登录用户时，会使用完整系统用户上下文投递延后后处理 Celery：`permissions=[]`、`roles=[]`、`user.userId=0`、`user.userName=system`；延后后处理入口也兼容历史只包含 `user` 的任务载荷。 |
| 5.1.7 | 主动拉取字段映射目标字段会将 `moduleName/module_name/ticketModel/ticket_model` 归一为 `ticketModle`，避免模块别名配置被外部同步必填校验误判为缺失。 |
| 5.1.8 | 主动拉取支持 `forceSync/force_sync`，开启后绕过本地 `recordId + snapshotHash` 跳过逻辑，重新执行入库与延后后处理；该参数不改变飞书查询范围，历史记录仍需通过 `createdAfter/filterFormula/viewId` 查到。 |
| 5.1.9 | 主动拉取映射出的 `ticketVender/ticketModle/internalOwner` 会保存到 `extraData.external_field_mapping`，并同步为 `projectName/moduleName/internalOwnerName` 给入库识别使用；主动拉取 `automation.autoTranslate` 优先于全局 `autoTranslateOnSync`。 |
| 5.1.10 | 主动拉取转换模型时会执行专用字段兜底：`ticketAssigneeName/assigneeName` 等别名会归一为当前处理人，并写入顶层模型和 `extraData.external_field_mapping`；优先级补齐规则已收敛为外部推送、主动拉取和远端拉取共用能力。 |
| 5.1.10.1 | 2026-07-21 起，外部推送、主动拉取和远端拉取统一使用优先级成对补齐规则：`Level 0/Level A/Level B/Level C/Level D` 分别转换为 `P0/P1/P2/P3/P4`；只有一侧为空时补齐缺失侧，双方都有值时各自保留。 |
| 5.1.11 | 主动拉取记录级必填校验直接使用“外部工单字段模型”中 `required=true` 的字段；字段不全时 `_build_bitable_pull_sync_object` 返回空，任务汇总计入 `failedCount`，不会进入 `sync_external_ticket`，因此不会入库或自动发群消息。 |
| 5.1.12 | 主动拉取识别飞书长文本富文本片段数组，按片段顺序拼接并保留 `"\n"` 为真实换行；空文本片段自然忽略，不再把换行或空片段 JSON 化为普通文本，保证描述格式和 `stepReason` 评论日期行分割不丢失。 |
| 5.1.13 | 2026-07-21 起，主动拉取人员字段转换会记录 `飞书多维表格主动拉取人员字段映射` 日志，展示 `reporterName/reporterEmail/currentAssignee/internalOwner` 等目标字段对应的多维源字段和脱敏邮箱；群推送 @ 解析会记录邮箱来源，并在候选姓名与邮箱查询到的飞书用户名不一致时输出 `群推送人员邮箱疑似错配`。2026-07-26 起，群推送邮箱解析新增从 `raw_payload.fields` 中按姓名匹配飞书人员对象提取邮箱的兜底层级，解决 bitable_pull 场景下 email 未映射到 external_field_mapping 且系统无对应用户时 @mention 为空的问题。 |
| 6 | 内网消费方调用 `GET /ticket/sync/pending` 时，控制器直接调用 `TicketSyncDeliveryService.pull_pending_tickets`，优先拿到 `external_sync.revision > consumers.{consumer}.delivered_revision` 且 `publish_ready=true` 的工单；若候选工单卡在 `processing_ai` 但没有活动 AI 任务，会先自动恢复发布状态再返回。 |
| 7 | 内网将远端 pending 工单转换为本地入库模型时，会优先读取 `moduleName/module_name`，并兼容 `ticketModle/ticketModel/ticket_model` 与 `extraData.external_field_mapping.ticketModle`，避免模块文本在跨环境二次同步时丢失。 |
| 7.1 | 远端拉取入库不会复用公网项目/模块/用户 ID，但已有本地工单会同步远端最新项目/模块文本并清空旧本地 ID；状态会使用内网本地 `statusMappings` 映射远端状态文本，并通过 `assigneeMappings`、邮箱或姓名解析当前处理人、报告人和内部负责人；未命中时保留远端文本。 |
| 7.1.1 | 远端拉取链路由 `TicketRemoteSyncService` 和 `remoteSync.enabled` 控制，不会再次查询公网飞书多维表格；公网补齐后的邮箱会随 pending payload 带到内网，内网只做本地人员解析。该服务负责远端请求头构造、pending payload 转 `TicketExternalSyncUpsertModel`、本地 revision/time 跳过判断和 ack 回写，定时任务不再通过 `TicketSyncService` 转发。 |
| 7.2 | 外部 `stepReason` 会按 `20260616 人员：` 或 `20260616：` 拆分为同步评论；pending payload 携带同步评论，内网按 `sourceSegmentKey` 幂等写入，保留本地评论不被覆盖。 |
| 8 | pending 返回后，`TicketSyncDeliveryService` 先写入该消费方的 `status=pulled`、`last_revision`、`last_batch_id` 和 `last_pulled_at` 作为租约；成功 ack 后才推进 `delivered_revision`。 |
| 9 | 如果消费方还需要把“已处理”“处理失败”“部分成功”等结果反馈回公网环境，可调用可选接口 `POST /ticket/sync/ack`；控制器直接调用 `TicketSyncDeliveryService.ack_sync_delivery`，只有成功状态会推进 `delivered_revision`，失败状态只记录错误，保留同一 revision 下次重试。 |
| 10 | 同一工单后续只要再次从外部系统同步进入，`revision` 会继续递增，内网消费方下次仍可拉到新的版本；项目、模块、商家日志拉取提示等外部字段变化会随本次入库同步更新，不再沿用旧工单归属。 |
| 11 | 自动群推送采用”仅一次成功发送”标记：`group_push_sent_once=true` 后，即使后续是同工单更新也不会重复自动发群消息；手动发群不受此标记限制。 |
| 11.1 | 2026-07-25 起，自动群推送条件改为表达式引擎：`autoPushCondition` 是唯一过滤条件，支持字段比较、成员判断、空值判断、`has()` 函数和逻辑运算；旧的 `autoPushStatuses` 和 `autoSendAfterTime` 已移除。留空表示全部推送。2026-07-27 起，`status` 表示状态编码，新增 `status_name` 表示工作流状态显示名，中文状态条件必须使用 `status_name`。 |
| 12 | 飞书话题评论同步由 `ticket.sync.automation.messageSync` 控制，默认关闭；公网 webhook 由 `feishuEventEnabled` 控制并继续通过 `POST /ticket/webhook/feishu/message` 接收飞书消息事件；无公网长连接由 `feishuWsEnabled` 控制，服务启动时通过 `lark_oapi` 的 `lark.ws.Client` 监听 `im.message.receive_v1`。两种入站方式都按 `message_id` 生成评论幂等键写入 `ticket_comment`，并可按配置追加写回多维表格排查过程字段；入站发送人会优先用 `sender.open_id` 查询飞书用户详情并写入用户名，避免把 `open_id/union_id` 直接展示给用户；正文中的 `@_user_1` 会按 `mentions` 替换为 `@用户名`，并在 `attachments.content_segments` 保留人员 ID，供写回多维表格或飞书群时恢复真实 @。 |
| 13 | 群推送应用发送成功后会把飞书 `messageId/rootId/threadId/chatId` 写入 `ticket.extra_data.external_sync.sync_state.group_push_message_refs`，后续飞书事件优先按这些锚点匹配工单；历史无锚点消息会回退从文本识别工单号。 |
| 14 | 为避免“飞书评论写回多维表格后又被主动拉取”造成重复评论，评论同步会同时使用 `source_segment_key` 与 `source_content_hash` 去重；同一工单同一内容哈希已存在时跳过新增。 |
| 15 | 长连接监听使用后台守护线程运行，每条事件创建独立数据库会话；当前 SDK 只提供 `start()`，应用关闭时只能标记停止并等待进程退出释放连接。 |
| 16 | 人员催办预览、人员催办执行和工单汇总统计通知由 `TicketSyncNotificationJobService` 读取同步自动化配置并调用 `TicketSyncNotifyService`，不再通过 `TicketSyncService` 转发。 |
| 17 | 2026-07-04 起，工单服务按依赖关系移动到子包：本流程涉及的同步服务统一位于 `modules.ticket.service.sync`，AI、日志拉取、核心工单、协作、通知和统计能力分别位于 `service.ai`、`service.log_pull`、`service.core`、`service.collaboration`、`service.notification`、`service.stats`；流程调用方不再引用旧的 `modules.ticket.service.ticket_*` 顶层路径。 |
| 18 | `syncSummary` 构造、消费者状态更新、pending 拉取和 ack 回执已下沉到 `TicketSyncDeliveryService`；后续交付状态规则不再回填到 `TicketSyncService`。 |
| 19 | `POST /ticket/sync/auto-category/reclassify` 和 `GET /ticket/sync/auto-category/stats` 属于手动管理链路，由 `TicketBatchReclassificationService` 编排批量筛选、正则分类、AI 分类调度和未归类统计，不参与外部入库事务主路径。 |
| 20 | `POST /ticket/sync/external` 的请求体读取、外部字段必填校验、人员字段拆分、`external_field_mapping` 与 `raw_payload` 构造已下沉到 `TicketExternalSyncRequestService`；`TicketSyncService` 只接收已通过模型校验的同步对象执行入库主编排。 |

## 错误处理

| 场景 | 处理方式 |
|---|---|
| 外部同步缺少必填字段（`ticketNo`、`description`、`internalPriority`、`ticketVender`、`ticketModle`、`createTime`、`reporterName`） | 直接参数校验失败并记录日志，拒绝入站 |
| 自动识别无法确定项目/模块归属 | 保留原始项目/模块文本与同步元数据，识别步骤状态照常落库，不阻断同步主流程 |
| 自动拉日志或自动 AI 异常 | 在 `extra_data.external_sync.sync_state.automation` 中记录失败步骤和错误信息；AI 任务终态（成功/失败/取消）都会将 `publish_ready` 置为 `true`，不阻断入库数据最终发布 |
| 消费方拉取后自身处理失败 | failed 回执不会推进 `delivered_revision`，仅记录失败状态、失败 revision 和错误信息；下一次 pending 拉取仍可返回同一 revision 重试 |
| 飞书事件重复投递 | 使用飞书 `message_id` 构造 `source_segment_key`，重复事件只会命中已存在评论并跳过 |
| 飞书写回多维后被主动拉取 | 同一工单相同 `source_content_hash` 的评论不再重复新增 |
| 历史工单未记录话题锚点 | 飞书入站会回退按文本工单号匹配；系统评论回发话题会跳过并返回 `missing_group_message_anchor` |

## 参见

- [工单域](../entities/services/ticket-domain.md)
- [工单自动化链路流程](ticket-automation-flow.md)
- [HTTP API 入口流程](http-api-entrypoint.md)

## 被引用

- [内容目录](../index.md)
- [工单域](../entities/services/ticket-domain.md)
