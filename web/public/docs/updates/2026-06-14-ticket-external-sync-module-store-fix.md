---
title: 工单外部同步模块与门店信息修复
type: note
source_type: code
created: 2026-06-14
updated: 2026-06-15
---

# 工单外部同步模块与门店信息修复

## 背景

外部系统通过 `/ticket/sync/external` 推送工单时，模块字段来自约定字段 `ticketModle`。该字段可能成功映射为本地 `module_id/module_name`，也可能因为映射未配置、本地模块不存在或历史数据里的模块 ID 已失效而只能保留文本。

## 当前规则

1. 外部同步入库时，`ticketModle` 仍只在第三方直推边界参与模块映射。
2. 如果映射命中本地有效模块，则写入本地 `module_id` 和 `module_name`。
3. 如果映射失败、本地模块 ID 无效，或已有工单的模块名为空，则保留外部模块文本到 `module_name`。
4. 映射失败时不会写入错误的 `module_id`，保持“只写文本不写 ID”的既有语义。
5. 同步元数据 `extra_data.external_sync.source.moduleName` 会记录最终识别到的模块文本，便于排查外部推送和后续群消息、统计链路。
6. 工单群消息默认模板已补充门店变量 `门店：{store_info}`，同步成功后发群可看到门店信息。

## 本次补充

2026-06-15 修复已有工单重复外部推送时的模块名丢失问题：当传入或检测到的 `module_id` 查不到本地有效模块，且已有工单 `module_name` 为空时，落库 payload 会使用 `detected.moduleName` 或 `sync_object.module_name` 兜底写入 `module_name`。

示例：外部推送 `ticketModle = "POS - 客户端"`，但本地模块映射未命中或历史 `module_id` 无效时，工单表至少会保存：

```json
{
  "module_name": "POS - 客户端"
}
```

不会保存无效的 `module_id`。

## 多维表格邮箱诊断日志

2026-06-15 补充外部推送按 `recordId` 查询飞书多维表格邮箱的诊断日志，便于确认报告人、当前负责人、内部负责人邮箱分别在哪一步成功或失败。

日志会记录：

1. 是否跳过查询，例如未启用 `externalSyncBitable`、配置不完整、外部未传 `recordId`。
2. 是否开始调用飞书多维表格接口，以及返回的字段数量和字段名列表。
3. 三类邮箱的固定字段读取结果：`(IT) L1 PIC`、`当前负责人`、`1.5 当前负责人`。
4. 每个字段是否存在、字段值结构摘要、邮箱是否提取成功、失败原因。
5. 最终是否写入 `extraData.external_field_mapping`，以及写入了哪些邮箱键。

日志不输出飞书密钥、tenant token 和字段原始值；邮箱结果会脱敏展示。

## 涉及文件

- `server/modules/ticket/service/ticket_sync_service.py`
- `server/modules/ticket/service/ticket_sync_notify_service.py`
- `server/tests/test_ticket_sync_mapping_boundary.py`
