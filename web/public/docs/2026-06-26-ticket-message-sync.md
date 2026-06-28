# 2026-06-26 工单评论消息同步实现记录

## 结论

本次新增“飞书话题评论 -> 工单评论 -> 可选多维表格排查过程”的同步链路，并预留“工单系统评论 -> 多维表格 / 飞书话题”的配置开关。飞书入站同时支持公网 webhook 和官方 SDK 长连接两种方式；默认配置全部关闭，不会自动写正式多维表格。

## 实现范围

- 新增无登录态回调接口：`POST /ticket/webhook/feishu/message`，保留公网 webhook 订阅方式。
- 新增官方 SDK 长连接监听服务：`TicketFeishuEventListenerService`，使用 `lark_oapi` 的 `lark.ws.Client` 监听 `im.message.receive_v1`，不要求本服务具备公网地址。
- 新增配置段：`ticket.sync.automation.messageSync`。
- 飞书消息入站时：
  - 支持飞书 `challenge` 校验。
  - webhook 仅在 `messageSync.enabled=true` 且 `feishuEventEnabled=true` 时处理。
  - 长连接仅在 `messageSync.enabled=true` 且 `feishuWsEnabled=true` 时随服务启动。
  - `allowedChatIds` 非空时只处理指定群。
  - `ignoreBotOpenIds` 用于跳过机器人自己的消息，避免回环。
  - 优先按已记录的群推送 `messageId/rootId/threadId` 匹配工单；匹配不到再从文本提取工单号。
  - 入站消息会用 `sender.open_id` 查询飞书用户详情，把评论人解析为用户名后再写入工单评论和多维表格排查过程。
  - 使用飞书 `message_id` 生成 `source_segment_key` 写入 `ticket_comment`，保证事件重试不重复。
  - webhook 和长连接会转换为同一内部事件结构，复用同一套匹配、过滤、去重和写回逻辑。
- 群推送现在会记录飞书应用发送返回的 `messageId/rootId/threadId/chatId` 到 `ticket.extra_data.external_sync.sync_state.group_push_message_refs`，用于后续评论回帖定位话题。
- 评论去重除原有 `(ticket_id, source_segment_key)` 外，新增同工单 `source_content_hash` 查重，减少“飞书写回多维后再被定时拉取”导致的重复评论。

## 配置说明

`messageSync` 字段：

- `enabled`：评论同步总开关。
- `feishuEventEnabled`：飞书 webhook 事件入站开关，需要公网回调地址。
- `feishuWsEnabled`：飞书官方 SDK 长连接入站开关，不需要公网回调地址。
- `feishuWsVerificationToken`：飞书事件订阅 Verification Token，长连接注册事件处理器时传入，可按飞书应用配置填写。
- `feishuWsEncryptKey`：飞书事件订阅 Encrypt Key，长连接注册事件处理器时传入，可按飞书应用配置填写。
- `allowedChatIds`：允许处理的飞书群 chat_id 列表。
- `ignoreBotOpenIds`：需要忽略的机器人 open_id 列表。
- `syncFeishuCommentToTicket`：飞书评论是否写入工单评论，默认开启。
- `syncFeishuCommentToBitable`：飞书评论是否追加到多维表格排查过程，默认关闭。
- `syncTicketCommentToBitable`：工单系统本地评论是否追加到多维表格排查过程，默认关闭。
- `syncTicketCommentToFeishuThread`：工单系统本地评论是否回复到飞书话题，默认关闭。
- `syncBitableNewStepToFeishuThread`：多维表格新增排查过程是否同步到飞书话题，已预留开关，本次不主动执行。
- `bitableStepReasonField`：排查过程字段名，默认 `stepReason`。
- `appendStepReasonFormat`：追加到多维表格的文本格式，默认 `{date} {user}：{content}`。

## 对现有流程影响

- 外部工单入库、主动拉取、多维字段映射、自动识别、自动群推送主流程不变。
- webhook 方式继续保留；新增长连接方式只是新增一个入站通道，不改变现有 webhook URL 和响应格式。
- 服务启动时会读取一次同步配置；只有 `messageSync.enabled=true` 且 `feishuWsEnabled=true` 且飞书应用凭证完整时才启动后台长连接线程。
- 新增后端依赖 `lark-oapi`，依赖解析会引入 `pycryptodome`、`requests-toolbelt`，并将 `websockets` 锁定到 SDK 兼容版本。
- `ticket_comment` 继续使用现有唯一约束，不新增迁移表。
- 群推送应用发送会多保存飞书消息引用，不改变原有“只自动推送一次”的语义。
- 工单系统新增本地评论时，会检查 `messageSync` 开关；默认关闭时只多一次轻量配置读取，不会向外发消息。
- 多维主动拉取仍会拆 `stepReason` 为评论；新增内容哈希去重后，不同来源带回同一条内容时会跳过重复写入。

## 风险与回滚

- 飞书事件回调接口无登录态，必须只暴露给飞书事件订阅使用；上线前应在网关层限制来源或增加飞书签名校验。
- 官方 SDK 当前版本的 `ws.Client` 只有 `start()`，未提供显式 `stop/close`；应用关闭时服务会标记停止并记录日志，实际连接释放依赖进程退出或 SDK 内部异常退出。
- 若同时开启 webhook 和长连接，并且飞书后台两种方式都投递同一条消息，系统会按 `message_id` 幂等跳过重复评论，但仍会多一次事件处理开销。
- 写多维表格是正式数据写操作，开启 `syncFeishuCommentToBitable` 或 `syncTicketCommentToBitable` 前必须先在测试表验证。
- 若不希望系统评论外发，关闭 `syncTicketCommentToBitable` 和 `syncTicketCommentToFeishuThread` 即可回滚。
- 若飞书消息未能匹配工单，通常是历史工单缺少 `group_push_message_refs`，需要重新手动群推送或在消息文本中包含工单号。
