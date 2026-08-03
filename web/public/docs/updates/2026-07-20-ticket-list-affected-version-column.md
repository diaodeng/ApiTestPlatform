---
title: 工单列表新增影响版本列
type: doc
created: 2026-07-20
updated: 2026-07-20
tags:
  - ticket
  - list
  - version
---

# 工单列表新增影响版本列

## 变更内容

- 工单列表新增“影响版本”列，对应工单主表 `affected_version`。
- 列设置中新增“影响版本”可选项，用户可按需显示或隐藏。
- 列表返回装饰逻辑不再把 `affectedVersion` 强制覆盖成历史 `versionKey`，避免把真实发现问题版本和兼容字段混淆。

## 影响范围

- `web/src/views/ticket/index.vue`
- `web/src/views/ticket/hooks/useTicketList.js`
- `server/modules/ticket/service/core/ticket_service.py`

## 说明

- `affectedVersion` 仍兼容日志提取和历史数据回填。
- `versionKey` 保留为旧链路兼容字段，不再作为列表展示的主语义。
