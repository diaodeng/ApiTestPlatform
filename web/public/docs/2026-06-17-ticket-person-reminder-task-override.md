# 2026-06-17 按人催办定时任务覆盖配置

## 背景

按人催办通知原先只能从“工单同步配置”的 `personReminder` 读取飞书筛选条件、人员字段、时间字段、视图、`tableId`、`appToken` 等参数。多个定时任务需要读取不同多维表格或不同视图时，只能改全局配置，容易互相影响。

## 变更内容

1. 定时任务 `module_task.scheduler_maintenance.ticket_person_overdue_reminder` 支持任务级覆盖字段：`appToken`、`tableId`、`viewId`、`filterFormula`、`personField`、`timeField`、`dataSource`、`pageSize`。
2. 覆盖规则为“任务非空值优先”：任务 JSON 配了对应非空字段就使用任务值；未配置或为空字符串时继续使用全局 `personReminder` 配置。
3. 覆盖字段支持平铺写法，也支持放在 `personReminder` 对象中，便于任务参数分组。
4. 修复全员催办分支未返回执行结果的问题，并让全员催办同样走任务级覆盖配置。
5. 兼容单个邮箱字符串参数；只配置 `userId` 时也会执行一次单人催办。
6. `filterFormula` 恢复为飞书公式文本透传，兼容历史 JSON 字符串包裹公式，避免任务中配置普通公式文本时被 `json.loads` 误解析失败。

## 参数示例

平铺写法：

```json
{
  "isAll": true,
  "appToken": "bascnxxxx",
  "tableId": "tblxxxx",
  "viewId": "vewxxxx",
  "personField": "当前负责人",
  "timeField": "更新时间",
  "filterFormula": "CurrentValue.[状态] != \"已关闭\""
}
```

分组写法：

```json
{
  "email": ["a@example.com"],
  "personReminder": {
    "appToken": "bascnxxxx",
    "tableId": "tblxxxx",
    "personField": "处理人",
    "timeField": "创建时间"
  }
}
```

## 影响范围

1. 后端定时任务入口：`server/module_task/scheduler_maintenance.py`。
2. 人员催办服务配置合并：`server/modules/ticket/service/ticket_sync_service.py`。
3. 飞书多维表格查询过滤公式处理：`server/modules/ticket/service/ticket_sync_notify_service.py`。
