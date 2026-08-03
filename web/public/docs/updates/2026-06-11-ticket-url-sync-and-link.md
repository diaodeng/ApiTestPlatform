# 2026-06-11 工单详情链接贯通（外部推送 + 内网拉取 + 页面跳转 + 群推送变量）

## 结论

- 新增工单字段 `ticket_url`，用于持久化外部工单详情链接。
- 外部推送与内网拉取都支持同步该链接。
- 工单列表/详情页新增“跳转/打开详情”入口，可直达外部工单页面。
- 群推送模板新增可用变量 `${ticket_url}`（并保留 `${sync_source_record_url}`）。

## 后端改动

- 数据模型
  - `server/modules/ticket/entity/do/ticket_do.py`
    - `Ticket` 新增列：`ticket_url`（`String(1000)`，可空）。
  - `server/modules/ticket/entity/vo/ticket_vo.py`
    - `TicketBaseModel` 新增字段：`ticket_url`。

- 外部推送入参归一化
  - `server/modules/ticket/controller/ticket_controller.py`
    - 兼容读取 `url/ticketUrl/detailUrl`，写入 `ticket_url`。
    - `source.record_url` 在缺失时回退到该链接。

- 同步服务链路
  - `server/modules/ticket/service/ticket_sync_service.py`
    - `extract_sync_summary` 补充 `sourceRecordUrl/ticketUrl`。
    - `_build_upsert_payload` 将链接回填到 `ticket_url` 并写入同步元数据。
    - `_merge_external_text_fields` 同步维护 `source.ticketUrl`。
    - `_build_remote_sync_upsert_model` 拉取侧兼容 `ticketUrl/ticket_url/url/detailUrl` 并回填。

- 群推送变量
  - `server/modules/ticket/service/ticket_sync_notify_service.py`
    - 默认模板增加 `链接：${ticket_url}`。
    - 模板变量新增 `ticket_url` 与 `sync_source_record_url`。

## 前端改动

- 工单列表/详情页
  - `web/src/views/ticket/index.vue`
    - 列表操作区新增“跳转”按钮（有链接时显示）。
    - 详情描述区新增“外部链接 -> 打开详情”。
    - 新增 `resolveTicketDetailUrl/openTicketLink` 逻辑，统一兜底取值来源。

- 同步配置页提示
  - `web/src/views/ticket/syncAutomation/index.vue`
    - 群推送模板提示补充 `${ticket_url}` `${sync_source_record_url}`。

## SQL 变更

- 新增迁移脚本：`server/sql/20260611_ticket_add_ticket_url.sql`
  - 为 `ticket` 表新增 `ticket_url` 字段（可空）。

