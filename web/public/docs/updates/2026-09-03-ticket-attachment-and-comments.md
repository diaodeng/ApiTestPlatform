# 2026-09-03 工单附件展示与评论来源扩展

## 变更主题

工单附件（多维表格附件字段）同步与展示、一线回复（L1 Response）评论、多维表格记录评论拉取（预留）、排查过程评论时间边界修正。

## 变更内容

### 1. 工单附件同步与查看（方案A：fileToken + 实时换链）

- 外部字段模型新增目标字段 `ticketAttachments`（工单附件）与 `replyAttachments`（答复附件），分类 `attachment`。
- `FeishuBitableUtil` 新增 `extract_attachment_tokens`：从附件字段提取 `fileToken/name/size/type` 结构化信息，丢弃临时 URL（约 24 小时过期）。
- 主动拉取记录转换时附件字段转移到 `ticket.extra_data.bitable_attachments` 持久化，并参与快照哈希（替换文件会触发重同步）。
- 新增 `TicketAttachmentUrlService`（`modules/ticket/service/attachment/`）：按 fileToken 实时换取飞书临时下载链接，进程内 30 分钟缓存。
- 新增接口：
  - `GET /ticket/{id}/attachments`：附件元信息列表；
  - `GET /ticket/{id}/attachments/{fileToken}/url`：302 跳转临时链接。

### 2. 一线回复评论（L1 Response）

- 同步模型 `TicketExternalSyncUpsertModel` 新增 `l1_response` 字段（驼峰 `l1Response`，兼容 Celery 序列化往返）。
- `TicketSyncCommentService` 泛化为多字段分段评论同步（`SUPPORTED_SEGMENT_FIELDS = (stepReason, l1Response)`），公共化为 `_sync_single_segment_field`。
- l1Response 评论正文末尾追加【一线回复】文案，`attachments.sourceFieldLabel` 记录来源标签，前端显示绿色标签。
- 幂等键参数化：`build_step_reason_segment_key` 新增 `source_field` 参数；**stepReason 保持历史键结构不变**（已入库评论不重复），l1Response 键中拼入字段名。

### 3. 排查过程评论时间边界修正

- `parse_step_reason_date`：解析日期等于服务器本地"今天"时返回 `None`，评论时间落到入库时刻；非当天维持 `00:00:00`。
- 仅影响增量同步；存量评论不回填。

### 4. 多维表格记录评论拉取（预留）

- 新增 `TicketBitableRecordCommentService`（`modules/ticket/service/sync/ticket_bitable_record_comment_service.py`）：
  - 幂等键 `sha256("bitable_comment|{record_id}|{comment_id}")`；
  - 评论人 open_id 解析姓名；附件元素提取 fileToken；
  - **重要**：截至 2026-09 飞书 bitable 服务端 API 无"记录评论"接口（官方 SDK 1.6.9 资源清单与概览文档确认仅 8 类资源；真实环境探测各路径均 404）。端点做成可配置（`messageSync.bitableRecordCommentApiPath`），404 时记录警告并安全跳过；API 上线后配置真实路径即可启用。
- `messageSync` 新增配置：`syncBitableRecordComments`（默认 false）、`bitableRecordCommentMaxTickets`（默认 200）、`bitableRecordCommentApiPath`。
- 新增手动接口 `POST /ticket/sync/automation/bitable-record-comments/run`；定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_record_comments`。

### 5. 前端

- 评论列表（`TicketDetailCommentsTab.vue`）：一线回复标签、评论附件展示（图片内联预览、文件下载链接）。
- 概览页（`TicketDetailOverviewTab.vue`）：新增"工单附件"卡片（有附件时显示）。
- API 封装（`web/src/api/ticket/ticket.js`）：`getTicketAttachments`、`buildTicketAttachmentUrl`、`runBitableRecordCommentPull`。

## 涉及文件

- `server/modules/ticket/service/sync/ticket_sync_comment_service.py`
- `server/modules/ticket/service/sync/ticket_bitable_pull_service.py`
- `server/modules/ticket/service/sync/ticket_bitable_record_comment_service.py`（新增）
- `server/modules/ticket/service/attachment/ticket_attachment_url_service.py`（新增）
- `server/modules/ticket/service/sync/ticket_sync_config_service.py`
- `server/modules/ticket/util/ticket_feishu_bitable_util.py`
- `server/modules/ticket/entity/vo/ticket_vo.py`
- `server/modules/ticket/controller/ticket_crud_controller.py`
- `server/modules/ticket/controller/ticket_sync_controller.py`
- `server/module_task/scheduler_maintenance.py`
- `server/tests/test_ticket_comment_and_attachment_sync.py`（新增，17 用例）
- `web/src/api/ticket/ticket.js`
- `web/src/views/ticket/components/detail-tabs/TicketDetailCommentsTab.vue`
- `web/src/views/ticket/components/detail-tabs/TicketDetailOverviewTab.vue`
- `web/public/docs/ticket/ticket-attachment-comments.md`（新增用户说明）

## 验证记录

- `ruff check`：本次改动文件全部通过（config_service 的 11 个 E501 为存量）。
- 新增 17 个单测全部通过；全量回归中 13 个失败用例经 stash 对照确认为存量问题（与本次改动无关）。
- 前端 `vite build` 成功。
- 使用 `.env.prod` 真实配置做只读端到端验证（未写库、未写飞书）：
  - prod 同步配置读取正常（bitablePull 启用、15 条映射）；
  - 真实记录 `(IT)工单附件` 提取成功（fileToken/name/size）；
  - 记录评论接口按预期 404 → 警告日志 + 0 条，任务不中断。
