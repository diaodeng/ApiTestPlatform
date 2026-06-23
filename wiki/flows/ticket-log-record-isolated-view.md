---
title: 工单日志拉取记录独立查看流程
type: flow
source_type: code
created: 2026-06-23
updated: 2026-06-23
related_files:
  - server/modules/ticket/service/ticket_log_service.py
  - server/modules/ticket/controller/ticket_controller.py
  - server/modules/ticket/entity/vo/ticket_log_pull_vo.py
  - web/src/api/ticket/ticket.js
  - web/src/views/ticket/index.vue
---

# 工单日志拉取记录独立查看流程

同一个工单存在多条日志拉取记录时，日志查看必须按“工单 + 拉取记录”定位。指定 `recordId` 查看时，后端使用 `data/logs/ticket_{ticketId}/record_{recordId}` 作为准备目录；未指定记录时继续兼容旧的 `data/logs/ticket_{ticketId}`。

## 关键规则

- `POST /ticket/logs/prepare` 接收 `ticketId + recordId`，并校验指定记录必须属于当前工单。
- 日志文件列表、关键字搜索、时间搜索、上下文读取、异常摘要都继续携带 `recordId`，避免搜索和翻页回到工单级旧目录。
- 同一记录已准备过 `extract` 目录时直接复用，不重复下载或解压。
- 日志拉取成功后，原始压缩包保存到记录自己的本地/FTP 归档路径；带时间范围时再截取正文入库，未带时间范围时只归档整包。
- AI 分析请求带 `logPullRecordId` 时使用指定记录；未带时取工单最新一条日志拉取记录，只有版本号缺失时才额外用最近成功记录兜底。
- 前端从某条日志拉取记录打开查看器后发起 AI 分析，会默认把该记录 ID 写入 `logPullRecordId`。

## 影响

该流程只改变日志查看器和从当前日志记录发起 AI 分析时的记录选择，不改变日志拉取、重新拉取、重新下载或归档下载语义。
