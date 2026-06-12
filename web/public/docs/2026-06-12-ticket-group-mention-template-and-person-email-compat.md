# 2026-06-12 工单群消息 @人模板配置与人员邮箱兼容补充

## 背景

外部推单/远端拉取发群时，需按模板判断是否 `@` 报告人与当前责任人；同时外部数据里的人员字段可能是对象（如 `reporterName/currentAssigneeName` 内含 `email`），需要稳定提取邮箱换取飞书 `open_id`。

## 本次补充

1. 外部同步入参归一化兼容“人员对象字段”：
   - `reporterName/currentAssigneeName/ticketAssignee` 支持字符串、对象、数组对象。
   - 可从对象中提取 `name/email`（兼容 `mail/userEmail/workEmail`）。
   - 提取结果会继续沉淀到 `extra_data.external_field_mapping`，供通知链路复用。
1. 群消息 `@` 邮箱解析补强：
   - 报告人邮箱新增支持从 `reporterName/reporter_name` 对象中提取。
   - 责任人邮箱新增支持从 `currentAssigneeName/current_assignee_name` 对象中提取。
1. 模板变量识别补强：
   - 新增变量别名支持：`reporter`、`ticketAssignee`、`ticket_assignee`、`currentAssignee`、`current_assignee`。
   - 允许占位符带空格，如 `${ reporterName }`。

## 模板如何配置才能 @到人

1. 只 @报告人：模板包含 `${reporterName}`（或 `${reporter_name}` / `${reporter}`）。
1. 只 @当前责任人：模板包含 `${currentAssigneeName}`（或 `${current_assignee_name}` / `${assignee_name}` / `${ticketAssignee}`）。
1. 同时 @两人：模板同时包含报告人与责任人变量。
1. 不需要 @：模板不包含上述变量。

## 生效范围与边界

1. 外部推单与远端拉取都生效：两条链路最终都走 `TicketSyncNotifyService.send_group_message_for_ticket`。
1. 手动推送不受自动去重影响；但若手动模板含上述变量，同样会触发 `@` 解析。
1. 若邮箱缺失或无法换取 `open_id`，自动降级为只发文本，不阻断群消息发送。
