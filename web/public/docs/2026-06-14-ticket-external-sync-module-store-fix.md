---
title: 工单外部同步模块与门店信息修复
type: note
source_type: code
created: 2026-06-14
updated: 2026-06-14
---

# 工单外部同步模块与门店信息修复

1. 外部同步入库时补充了模块字段兼容，`ticketModle` 现在同时兼容 `moduleName/module_name/moduleCode/module_code`，避免外部系统改传字段名后导致系统模块未写入。
2. 工单群消息默认模板补充了 `门店：${store_info}`，不会再出现同步成功但群消息里看不到门店信息的情况。
3. 本次修复未改动群推送路由、去重与异步后处理逻辑，仅补齐字段识别和模板展示。

## 涉及文件

- `server/modules/ticket/service/ticket_sync_service.py`
- `server/modules/ticket/service/ticket_sync_notify_service.py`

