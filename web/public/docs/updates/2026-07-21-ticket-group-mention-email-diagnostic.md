# 工单群推送一线人员 @ 邮箱错配排查记录

## 背景

2026-07-21 排查主动拉取工单群推送时发现：群推送日志中 `reporter` 的 `name` 正确，但 `email` 可能来自其他人员，导致飞书 `@` 到错误人员；也存在邮箱为空导致无法解析飞书 `open_id` 的情况。

## 当前结论

- `bitable_pull` 场景下，人员姓名和邮箱都来自主动拉取字段映射。
- `reporterName` 和 `reporterEmail` 可以配置为不同的多维表格源字段，系统此前不会校验二者是否属于同一个飞书人员对象。
- 群推送 @ 解析优先使用 `raw_payload` 或 `extra_data.external_field_mapping` 中的邮箱字段；如果邮箱错配，会按错误邮箱查询飞书 `open_id` 并 @ 错人。
- 如果邮箱为空，群推送只能回退按系统用户姓名查邮箱；外部英文姓名未维护为系统用户时，会无法生成 @。

## 本次日志增强

- `TicketBitablePullService.log_bitable_pull_person_mapping` 新增主动拉取人员字段映射日志，记录每个人员目标字段对应的多维源字段、源字段结构摘要和转换值，邮箱会脱敏。
- `TicketSyncNotifyService._resolve_ticket_person_email` 新增群推送人员邮箱来源日志，区分邮箱来自 `raw_payload`、`external_field_mapping` 还是系统用户姓名回退。
- `TicketSyncNotifyService._resolve_group_mention_open_ids` 新增邮箱疑似错配告警：当候选姓名与邮箱查询到的飞书用户名不一致时输出 `群推送人员邮箱疑似错配`。

## 排查方式

按工单号检索：

```powershell
rg -n "INC00001755291|飞书多维表格主动拉取人员字段映射|群推送人员邮箱解析|群推送人员邮箱疑似错配|群推送消息内容" server/logs logs
```

重点看：

- `reporterName` 与 `reporterEmail` 的 `sourceField` 是否相同或是否应来自同一个人员字段。
- `reporterEmail` 是否为空，或是否映射到了当前负责人、一线 PIC 之外的字段。
- `群推送人员邮箱疑似错配` 中 `candidate_name` 与 `feishu_user_name` 是否不一致。

## 后续建议

- 配置层优先保证 `reporterName` 和 `reporterEmail` 映射到同一个飞书人员字段。
- 如果多维表格只提供人员 `open_id` 而没有邮箱，后续可扩展群推送直接使用人员字段中的 `id/open_id`，减少对邮箱的依赖。
