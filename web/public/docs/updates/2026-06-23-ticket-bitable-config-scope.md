# 2026-06-23 工单多维表格与翻译配置边界

## 变更背景

同步自动化页面填写“多维表格公共配置”后，“飞书多维表格主动拉取”里的 `appToken/tableId/viewId/filterFormula` 会被自动回显填上。实际业务期望是：主动拉取配置保持独立；运行时如果独立配置为空，才继承公共配置。

## 本次结论

- 保存态/页面回显：公共多维配置不再写入外部推送邮箱补齐、按人催办、汇总统计、主动拉取等独立配置段。
- 运行态/执行链路：继续按“独立配置优先，独立为空才继承公共配置”解析。
- 任务参数或页面预览传入空字符串时，不会覆盖已经从公共配置继承的运行时值。

## 多维表格配置边界

| 链路 | 独立配置位置 | 可独立控制项 | 公用/继承项 | 优先级 |
|---|---|---|---|---|
| 外部推送邮箱补齐 | `ticket.sync.automation.externalSyncBitable` | `enabled`、`appId`、`appSecret`、`appToken`、`tableId`、`viewId` | 为空时继承 `bitableCommon.appId/appSecret/appToken/tableId/viewId`；`appId/appSecret` 还可回退 `feishuAuth` | 独立配置 > 多维公共配置 > 飞书统一凭证 |
| 内部拉取 | `ticket.sync.automation.remoteSync` | `enabled`、拉取地址、回写地址、消费者、请求头、批量数量、是否包含关闭工单、拉取后翻译 | 不查询飞书多维表格，不继承 `bitableCommon` | 只使用 `remoteSync` 自己的配置 |
| 多维表格主动拉取 | `ticket.sync.automation.bitablePull` | `enabled`、`appId`、`appSecret`、`appToken`、`tableId`、`viewId`、`pageSize`、`filterFormula`、字段映射、来源系统、创建时间窗口、自动化开关 | 为空时继承 `bitableCommon.appId/appSecret/appToken/tableId/viewId/pageSize/filterFormula`；`appId/appSecret` 还可回退 `feishuAuth` | 任务覆盖非空项 > 独立配置 > 多维公共配置 > 飞书统一凭证 |
| 手动新增/编辑 | 工单新增/编辑表单 | 是否自动翻译、是否自动拉日志、是否自动 AI 等表单自动化项 | 不使用飞书多维表格公共配置 | 表单入参独立控制 |
| 按人催办 | `ticket.sync.automation.personReminder` | 启用、发送方式、数据源、推送目标、飞书凭证、多维表、人员字段、时间字段、阈值、模板、分页 | 数据源为 `bitable` 且多维参数为空时继承 `bitableCommon`；任务参数非空可覆盖 | 任务覆盖非空项 > 独立配置 > 多维公共配置 > 飞书统一凭证 |
| 汇总统计 | `ticket.sync.automation.summaryReport` | 启用、发送方式、数据源、推送目标、统计字段、AI 汇总、时间窗口、模板、多维表参数 | 数据源为 `bitable` 且多维参数为空时继承 `bitableCommon` | 独立配置 > 多维公共配置 > 飞书统一凭证 |

## 翻译配置边界

| 链路 | 场景开关 | 全局依赖 | Provider/Prompt 来源 | 说明 |
|---|---|---|---|---|
| 外部推送 | `ticket.sync.automation.autoTranslateOnSync` | `ticket.ai.translate.enabled` | AI 配置中心：`ticket.ai.translate.provider.code`、`ticket.ai.translate.prompt.code` | 外部推送没有独立 Provider/Prompt，只控制该链路是否自动翻译 |
| 内部拉取 | `ticket.sync.automation.remoteSync.autoTranslateOnPull`，入库模型也会携带 `automation.autoTranslate` | `ticket.ai.translate.enabled` | AI 配置中心 | 内部拉取独立控制是否翻译，不继承外部推送开关 |
| 多维表格主动拉取 | `ticket.sync.automation.bitablePull.automation.autoTranslate` | `ticket.ai.translate.enabled` | AI 配置中心 | 主动拉取入库时通过同步模型传入自己的翻译开关 |
| 手动新增/编辑 | 工单表单 `autoTranslate` | `ticket.ai.translate.enabled` | AI 配置中心 | 手动链路由表单自己控制，不使用同步自动化页的 `autoTranslateOnSync` |
| 手动点击“翻译” | 工单详情按钮 | `ticket.ai.translate.enabled` | AI 配置中心 | 用户显式触发，不受各自动链路场景开关限制 |

## 代码落点

- `server/modules/ticket/service/ticket_sync_service.py`
  - `_normalize_sync_config` 只清洗保存态，不再把公共多维配置写入业务配置段。
  - `_resolve_bitable_runtime_config` 在执行查询前解析继承关系。
  - `_merge_non_empty_runtime_override` 保证任务/预览的空字符串不会覆盖公共继承值。
- `server/tests/test_ticket_sync_mapping_boundary.py`
  - 增加保存态不污染独立配置的断言。
  - 增加运行态继承公共配置的断言。

## 风险说明

历史数据库中如果已经保存了被公共配置污染后的独立配置值，本次不会自动清空这些值。原因是无法可靠判断该值是用户主动填写还是旧逻辑回写。需要用户在页面手动清空独立配置后保存，后续不会再被公共配置自动填回。
