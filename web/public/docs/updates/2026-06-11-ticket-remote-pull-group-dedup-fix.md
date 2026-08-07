# 2026-06-11 远端拉取链路群推送去重状态覆盖修复

## 背景

现象：内网服务“拉取公网工单后推群消息”出现重复推送，几乎每次拉取都会再次发群。

## 根因

远端拉取入库时会合并远端 `extraData`。远端数据里可能带有 `external_sync`，在本地更新时覆盖了本地 `external_sync.sync_state`，导致本地已写入的 `group_push_sent_once=true` 被覆盖丢失，后续再次满足自动推送条件时重复发送。

## 修复

在外部同步入库构建 payload 时，合并 `sync_object.extra_data` 前显式移除：

1. `external_sync`
1. `externalSync`

这样本地同步元数据（含 `group_push_sent_once/group_push_sent_at/group_push_revision`）不会被远端覆盖，自动推送去重可持续生效。

## 影响范围

1. 内网拉取公网工单（`sync_scene=remote_pull`）链路。
1. 外部同步更新场景中，携带 `external_sync` 的输入数据也不会覆盖本地同步状态。
