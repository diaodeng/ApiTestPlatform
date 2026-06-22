# 工单入库原文保留与 AI 分析版本号兜底

## 背景

外部工单入库时，项目、模块等归属字段可能无法命中本地 HRM 配置。如果匹配失败后只保存 ID，会导致页面展示和后续排查缺少原始业务文案。同时，工单版本号可能由人工先维护，后续外部更新未携带版本号时不应覆盖为空；发起 AI 分析时也需要支持在未手动选择版本号的情况下，从日志内容中自动提取版本号。

## 变更

1. 外部同步识别项目失败时，保留 `ticketVender/projectName/merchantName` 原始文本到 `merchant_name`，避免项目展示为空。
2. 模块匹配失败继续保留 `ticketModle/moduleName` 原始文本到 `module_name`，并补充项目原文同类测试。
3. 手动编辑工单时，如果请求没有版本号或版本号为空，不再删除已有 `extra_data.version_key`。
4. 发起 AI 分析时，版本号改为可选；用户手动选择版本号时优先使用手动值。
5. 未传版本号时，后端先读工单已有版本号；仍缺失时从指定日志记录或最近一条成功日志记录提取版本号，提取成功后回写工单，再按该版本号匹配仓库映射并提交 AI 分析。
6. 修正日志版本号回填链路中已解压文本被再次解码的问题，避免自动提取被异常跳过。

## 涉及文件

- `server/modules/ticket/service/ticket_sync_service.py`
- `server/modules/ticket/service/ticket_service.py`
- `server/modules/ticket/service/ticket_ai_analysis_service.py`
- `server/modules/ticket/service/ticket_log_pull_service.py`
- `server/modules/ticket/dao/ticket_log_pull_dao.py`
- `server/modules/ticket/entity/vo/ticket_vo.py`
- `web/src/views/ticket/index.vue`
- `server/tests/test_ticket_sync_mapping_boundary.py`

## 验证

已执行本次相关边界测试：

```bash
cd server
uv run python -m unittest tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_external_detection_keeps_project_text_when_mapping_misses tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_external_upsert_fills_project_name_from_detected_text tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_manual_update_keeps_existing_version_when_request_has_no_version tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_ai_analysis_extracts_version_from_log_when_request_missing tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_external_detection_keeps_module_text_when_mapping_misses tests.test_ticket_sync_mapping_boundary.TicketSyncMappingBoundaryTests.test_external_upsert_fills_empty_module_name_from_detected_text
```

结果：通过。

整文件测试 `uv run python -m unittest tests.test_ticket_sync_mapping_boundary` 仍存在既有断言失败：`test_sync_config_inherits_bitable_common_for_person_and_summary` 期望 `pageSize=123`，当前归一化结果为 `500`。该失败不在本次入库/版本/AI 分析链路内。
