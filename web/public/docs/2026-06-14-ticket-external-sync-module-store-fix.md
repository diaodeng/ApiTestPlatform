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

## 涉及文件

- `server/modules/ticket/service/ticket_sync_service.py`
- `server/modules/ticket/service/ticket_sync_notify_service.py`
- `server/tests/test_ticket_sync_mapping_boundary.py`
