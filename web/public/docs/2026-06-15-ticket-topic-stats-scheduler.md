# 2026-06-15 专题工单会话状态统计定时任务

## 背景

本次将 `D:\xj\Downloads\topic_ticket_stats.py` 的核心逻辑迁入当前项目，作为可配置的定时任务执行入口。任务通过 `lark-cli` 拉取指定飞书群在日期范围内的根消息，提取 Ticket、主题、专题分类和会话状态，并可按旧脚本格式发送飞书卡片。

## 新增能力

1. 新增服务：`server/modules/ticket/service/ticket_topic_stats_service.py`
   - 支持从定时任务参数传入飞书群来源、日期范围、`lark-cli` 路径、webhook、关键字和分页大小。
   - 统计口径保持脚本逻辑：只处理 `post`、`text` 根消息、提取 `Ticket:` 或 INC/SCTASK 编号、按主题归类为促销/券/会员/印花、按关键字判断有结论/无结论。
   - 日志覆盖每个关键步骤：任务开始、来源处理、分页拉取、命中/跳过原因、汇总结果和卡片发送返回。

2. 新增定时任务入口：`module_task.scheduler_maintenance.ticket_topic_stats_report`
   - 入口只负责参数归一化、手动终止检查和调度级日志。
   - 业务逻辑下沉到工单服务，避免调度文件堆积复杂逻辑。

## 完整定时任务配置示例

任务注册键：

```text
module_task.scheduler_maintenance.ticket_topic_stats_report
```

关键字参数：

```json
{
  "startDate": "2026-06-15",
  "endDate": "2026-06-15",
  "keyword": "TRunner",
  "send": true,
  "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/0a27950f-0c61-4df6-8e4e-2e683330505e",
  "larkCliBin": "C:\\nvm4w\\nodejs\\lark-cli.cmd",
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

完整新增任务对象示例：

```json
{
  "taskName": "专题工单会话状态统计",
  "taskKey": "module_task.scheduler_maintenance.ticket_topic_stats_report",
  "queueName": "sys",
  "executionMode": "thread",
  "scheduleType": "crontab",
  "cronExpression": "0 18 * * *",
  "taskArgs": "[]",
  "taskKwargs": "{\"startDate\":\"2026-06-15\",\"endDate\":\"2026-06-15\",\"keyword\":\"TRunner\",\"send\":true,\"webhook\":\"https://open.feishu.cn/open-apis/bot/v2/hook/0a27950f-0c61-4df6-8e4e-2e683330505e\",\"larkCliBin\":\"C:\\\\nvm4w\\\\nodejs\\\\lark-cli.cmd\",\"pageSize\":50,\"sources\":[{\"name\":\"RTA POS P0/P1 事故\",\"chatId\":\"oc_78ce6aaf8084d375b14946c094db3a9e\",\"priority\":\"P1\"},{\"name\":\"RTA POS P2 工单群\",\"chatId\":\"oc_fd391a88b21ebcafc3d1d69356909147\",\"priority\":\"P2\"},{\"name\":\"RTA POS P3/P4工单群\",\"chatId\":\"oc_15203ab07d26c830240fdb9caa8de501\",\"priority\":\"P3\"}]}",
  "enabled": true,
  "allowConcurrent": false,
  "lockTtlSeconds": 3600,
  "timezone": "Asia/Shanghai",
  "remark": "统计飞书工单群促销、券、会员、印花专题会话状态，并发送飞书卡片"
}
```

## 参数说明

- `startDate` / `endDate`：可选，格式 `YYYY-MM-DD`；不传时取上海时区当天。
- `sources`：必填，飞书群来源列表；每项必须包含 `name`、`chatId` 或 `chat_id`、`priority`。
- `send`：是否发送飞书卡片；为 `true` 时必须配置 `webhook`。
- `webhook`：飞书机器人 webhook。
- `keyword`：卡片副标题关键字，默认 `TRunner`。
- `larkCliBin`：可选，指定 `lark-cli` 路径；不传时依次尝试环境变量 `LARK_CLI_BIN`、`lark-cli.cmd`、`lark-cli` 和 Windows 默认路径。
- `pageSize`：单页拉取消息数量，范围会被限制在 1 到 100。

## 验证

已执行：

```bash
cd server
uv run python -m py_compile module_task\scheduler_maintenance.py modules\ticket\service\ticket_topic_stats_service.py
uv run ruff check module_task\scheduler_maintenance.py modules\ticket\service\ticket_topic_stats_service.py
```

未执行真实飞书拉取和 webhook 发送，原因是该验证会访问实际飞书群消息并发送真实机器人消息，需要部署环境具备 `lark-cli` 登录态和明确发送窗口。
