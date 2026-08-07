# 2026-06-17 专题工单统计改为飞书 API

## 背景

`module_task.scheduler_maintenance.ticket_topic_stats_report` 原先依赖本机 `lark-cli` 拉取群消息。本次改为后端直接调用飞书开放 API：用任务参数中的飞书应用 `appId` / `appSecret` 获取 `tenant_access_token`，再拉取群消息、统计专题工单信息，并通过飞书应用发送卡片消息。

## 变更内容

1. `server/modules/ticket/service/ticket_topic_stats_service.py`
   - 删除 `lark-cli` 路径解析和子进程执行链路。
   - 新增飞书 tenant token 缓存、开放 API JSON 请求封装。
   - 通过 `/im/v1/messages` 按群 `chat_id`、日期窗口和分页参数拉取群消息。
   - 对飞书消息结构做归一化，兼容 `data.items` / `data.messages`、`body.content` / `content`、秒级或毫秒级 `create_time`。
   - 根消息命中后继续按 thread 拉取回复，用于判断“有结论/无结论”。
   - 卡片发送改为飞书应用身份调用 `/im/v1/messages`，不再使用机器人 webhook。

2. `server/module_task/scheduler_maintenance.py`
   - `ticket_topic_stats_report` 新增 `appId` / `appSecret` / `receiveChatIds` 参数解析。
   - 移除 `larkCliBin` 和 `webhook` 参数链路。
   - `receiveChatIds` 为空且 `send=true` 时，默认发送到 `sources` 中配置的群。

## 任务参数示例

```json
{
  "startDate": "2026-06-17",
  "endDate": "2026-06-17",
  "appId": "cli_xxx",
  "appSecret": "xxx",
  "keyword": "TRunner",
  "send": true,
  "receiveChatIds": [
    "oc_78ce6aaf8084d375b14946c094db3a9e"
  ],
  "pageSize": 50,
  "sources": [
    {
      "name": "RTA POS P0/P1 事故",
      "chatId": "oc_78ce6aaf8084d375b14946c094db3a9e",
      "priority": "P1"
    },
    {
      "name": "RTA POS P2 工单群",
      "chatId": "oc_fd391a88b21ebcafc3d1d69356909147",
      "priority": "P2"
    },
    {
      "name": "RTA POS P3/P4工单群",
      "chatId": "oc_15203ab07d26c830240fdb9caa8de501",
      "priority": "P3"
    }
  ]
}
```

## 注意事项

- 飞书应用需要具备读取群历史消息和发送消息的权限，并且机器人需要在目标群内。
- `receiveChatIds` 可不传；不传时统计卡片会发送到所有 `sources.chatId`。
- 本任务不再读取 `LARK_CLI_BIN`，也不再要求本机存在 `lark-cli` 登录态。

