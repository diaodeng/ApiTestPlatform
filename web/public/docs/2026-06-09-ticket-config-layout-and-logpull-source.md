# 2026-06-09 工单配置页与日志拉取联动调整

## 本次改动

- 修复 AI 配置中心和工单同步配置页在部分布局下被压缩成窄条的问题。
- 日志拉取、工单日志拉取记录页的商家/门店联动选项改为直接从 `ticket_log_pull_store_config` 聚合，不再读取系统参数里的商家门店配置。

## 影响范围

- 前端：
  - `web/src/views/system/aiconfig/index.vue`
  - `web/src/views/ticket/syncAutomation/index.vue`
- 后端：
  - `server/modules/ticket/service/ticket_log_pull_service.py`

## 说明

- 联动接口返回结构保持不变，仍然是 `vendorId/vendorCode/vendorName` + `stores[]`。
- 前端现有商家/门店下拉逻辑可以继续复用，不需要改接口调用。
