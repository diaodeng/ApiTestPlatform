# 工单同步配置页中文乱码修复

## 背景

2026-06-13 上午调整工单同步配置页与通知模板时，部分中文文案被错误写成 `????`，同时汇总统计区的表单绑定被串改，导致页面显示异常、配置项不可用。

## 本次修复

- 恢复 `web/src/views/ticket/syncAutomation/index.vue` 中远端同步、外部同步必填字段、汇总统计通知等区域的中文文案。
- 恢复工单汇总统计通知的 `startTime/endTime/messageTemplate` 绑定，避免误写到 `groupPush` 配置。
- 为“外部同步必填字段”补充可见候选字段下拉，同时保留 `allow-create`，支持直接录入自定义字段名。
- 修复 `ticket_sync_notify_service.py` 中新增催办明细模板与群消息 @ 变量相关注释、默认模板文案的乱码。

## 影响文件

- `web/src/views/ticket/syncAutomation/index.vue`
- `server/modules/ticket/service/ticket_sync_notify_service.py`
- `web/public/docs/2026-06-13-ticket-external-sync-required-fields-config.md`
- `web/public/docs/update_history.md`
