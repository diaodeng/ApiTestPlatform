# 2026-06-11 手动群推送去重状态对齐自动推送

## 背景

此前工单群推送存在行为差异：

1. 自动推送会依赖 `group_push_sent_once` 去重状态，已发送后不再自动发送。
1. 手动推送不依赖该状态，且不会回写该状态，导致可重复发送且与自动链路语义不一致。

## 改动

1. 手动推送默认改为遵循去重状态：
   - 当 `group_push_sent_once=true` 且未开启强制时，手动推送直接跳过。
1. 手动推送成功后回写去重状态：
   - 与自动推送一致，成功发送后写入 `group_push_sent_once/group_push_sent_at/group_push_scene/group_push_revision`。
1. 新增手动强制推送能力：
   - 手动接口新增 `forcePush`（默认 `false`）。
   - `forcePush=true` 时允许忽略“已推送”状态继续发送。
1. 前端“手动触发入口”新增“强制推送”开关并适配跳过提示。

## 影响范围

1. 手动接口 `POST /ticket/sync/notify/group/send-by-ticket` 入参扩展 `forcePush`。
1. 自动推送链路继续依赖去重状态，不变。
1. 手动发送结果新增状态相关返回字段：`alreadySent`、`forcePush`、`groupPushSentOnceUpdated`。
