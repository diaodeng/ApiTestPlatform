# 2026-06-10 工单人员催办配置兜底与统计来源说明

## 结论

- 汇总通知（`summaryReport`）的统计来源是本地数据库 `ticket` 表，不依赖飞书多维表格。
- 人员催办（`personReminder`）的数据来源是飞书多维表格记录。
- 人员催办预览/手动执行在关键配置缺失时不再抛异常，改为返回 `skipped=true` 与可读 `skipReason`。

## 改动点

- 文件：`server/modules/ticket/service/ticket_sync_notify_service.py`
- 新增：
  - `_validate_person_reminder_config`：统一校验 `appId/appSecret`、`appToken/tableId`、`personField`、`timeField`。
  - `_build_person_reminder_skipped_result`：统一构建跳过结果，包含 `skipReason/configErrors/personCount/overdueRecordCount` 等字段。
- 调整：
  - `preview_person_overdue_statistics`：先做配置校验，缺失时直接返回跳过结果。
  - `run_person_overdue_reminder`：先做配置校验，缺失时直接返回跳过结果。
  - `web/src/views/ticket/syncAutomation/index.vue`：当前端收到 `skipped=true` 时，直接提示 `skipReason`。

## 返回示例

```json
{
  "skipped": true,
  "skipReason": "人员字段(personField)未配置；时间字段(timeField)未配置",
  "configErrors": [
    "人员字段(personField)未配置",
    "时间字段(timeField)未配置"
  ],
  "personCount": 0,
  "overdueRecordCount": 0
}
```

## 影响范围

- 仅影响工单同步配置中的“人员催办预览/执行”接口返回行为。
- 不改变现有统计口径与发送逻辑，不影响群推送和汇总通知的主流程。
