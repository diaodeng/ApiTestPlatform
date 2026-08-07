# 2026-06-25 多维表格主动拉取群消息人员解析与日志补充

## 背景

定时任务 `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync` 主动拉取飞书多维表格后会触发工单群消息。部分记录发送时无法解析到人员 `open_id`，同时日志只记录发送结果，没有记录渲染后的消息正文，排查人员字段来源困难。

## 变更

1. 主动拉取字段映射在目标字段为 `reporterEmail/currentAssigneeEmail/ticketAssigneeEmail/internalOwnerEmail` 时，优先从飞书人员对象或人员数组的 `email/mail` 中提取邮箱。
2. 目标字段为 `reporterName/currentAssigneeName/ticketAssignee/internalOwner` 时，优先从飞书人员对象的 `name/text/value` 中提取显示名。
3. 群消息通知服务的邮箱解析增强为兼容字符串、人员对象、人员数组，以及包含邮箱的混合文本。
4. 群消息发送前新增日志 `群推送消息内容`，记录工单号、场景、发送模式、推送目标、@ 解析明细和最终渲染后的消息正文。

## 影响范围

1. 仅影响工单同步通知链路的人员邮箱解析和日志可观测性。
2. 不改变群消息发送目标、去重逻辑、状态条件、远端公网拉取入库策略。
3. 如果多维表格人员字段本身没有邮箱，仍会继续按姓名查本地系统用户邮箱作为兜底；本地也不存在时无法生成飞书 `open_id`，但消息正文会正常发送。

## 验证

新增单测覆盖：

1. 主动拉取能从飞书人员对象中分别提取姓名和邮箱。
2. 群消息邮箱解析能从嵌套人员对象数组中提取邮箱。
