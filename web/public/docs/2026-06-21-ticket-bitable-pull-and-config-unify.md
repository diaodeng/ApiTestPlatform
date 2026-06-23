# 工单主动拉取与多维配置统一说明

## 变更日期

- 2026-06-21

## 结论

- 新增“飞书多维表格主动拉取”能力，定时任务可按条件查询多维记录，再复用 `/ticket/sync/external` 既有入库与后处理链路。
- 新增“多维表格公共配置”，汇总统计、按人催办、外部推送邮箱补全、主动拉取默认继承该配置，局部配置可覆盖。
- 新增“外部工单字段模型”，外部推送必填字段下拉枚举与主动拉取字段映射目标字段统一来源于该模型。
- 主动拉取增加记录快照去重，同一 `recordId` 且映射后快照未变化时跳过，避免定时任务反复给同一工单递增同步版本。
- 配置页已进一步优化：主动拉取“多维字段”支持下拉选择加手动输入；下拉项可按当前配置实时预览一条表格记录字段生成。

## 后端改动

### 1. 多维表格公共配置

- 配置路径：`ticket.sync.automation.bitableCommon`
- 字段：
  - `appId/appSecret`
  - `appToken/tableId/viewId`
  - `pageSize`
  - `filterFormula`
- 继承规则：
  - `personReminder`
  - `summaryReport`
  - `externalSyncBitable`
  - `bitablePull`
  以上模块未显式填写时，自动继承公共配置。

### 2. 外部工单字段模型

- 配置路径：`ticket.sync.automation.externalFieldModel.fields`
- 用途：
  - 同步配置页“外部同步必填字段”下拉来源
  - 主动拉取“字段映射”的目标字段来源
- 设计说明：
  - 这里维护的是“字段全集”
  - `required=true` 表示该字段属于外部同步必填字段
  - 不再建议再维护一份独立的必填列表，避免重复配置漂移
- 字段示例：
  - `ticketNo`
  - `description`
  - `internalPriority`
  - `ticketVender`
  - `ticketModle`
  - `createTime`
  - `reporterName`
  - `currentAssigneeName`
  - `internalOwner`
  - `recordId`

### 3. 飞书多维表格主动拉取

- 配置路径：`ticket.sync.automation.bitablePull`
- 核心字段：
  - `enabled`
  - `appId/appSecret/appToken/tableId/viewId`
  - `pageSize/filterFormula`
  - `fieldMappings`
  - `sourceSystem`
  - `updatedAtField`
  - `includeRecordUrl`
  - `automation`
- 调度任务：
  - `module_task.scheduler_maintenance.pull_feishu_bitable_ticket_sync`
- 任务覆盖支持：
  - 可传平铺参数
  - 也可传 `bitablePull` 嵌套对象
  - 任务参数非空时优先于可视化配置
- 页面可用性：
  - “多维字段”支持下拉 + 手动输入
  - 点击“读取表格字段”会按当前配置拉一条记录并返回字段名，便于快速选择
  - 自动化四个开关文案已明确区分“自动识别/自动拉日志/自动 AI 分析/自动翻译”

### 4. 主动拉取入库流程

1. 定时任务读取 `bitablePull` 配置。
2. 使用飞书多维表格 `records/search` 按配置条件拉取记录。
3. 根据 `fieldMappings` 将多维字段转换为外部同步字段。
4. 转为 `TicketExternalSyncUpsertModel`。
5. 复用 `TicketSyncService.sync_external_ticket(..., sync_scene="external_sync")` 入库。
6. 若 Celery 不可用，则同步回退本地后处理。

### 5. 主动拉取去重

- 元数据位置：`ticket.extra_data.bitable_pull`
- 关键字段：
  - `recordId`
  - `snapshotHash`
  - `fieldMappings`
  - `sourceSystem`
  - `pulledAt`
- 跳过条件：
  - 本地已有相同 `recordId`
  - 且当前映射后的 `snapshotHash` 与历史一致
- 跳过原因：
  - `snapshot_not_changed`

## 前端改动

### 工单同步配置页新增区块

- 多维表格公共配置
- 外部工单字段模型
- 飞书多维表格主动拉取

### 配置页行为

- 外部同步必填字段下拉改为读取“外部工单字段模型”
- 主动拉取字段映射的目标字段也读取同一模型
- 外部推送邮箱补全提示文案补充“未填写时继承公共多维配置”

## 定时任务参数示例

```json
{
  "bitablePull": {
    "enabled": true,
    "appToken": "bascnxxxx",
    "tableId": "tblxxxx",
    "viewId": "vewxxxx",
    "filterFormula": {
      "conjunction": "and",
      "conditions": [
        {
          "field_name": "是否入库",
          "operator": "is",
          "value": false
        }
      ]
    },
    "fieldMappings": [
      { "sourceField": "工单号", "targetField": "ticketNo" },
      { "sourceField": "标题", "targetField": "title" },
      { "sourceField": "描述", "targetField": "description" },
      { "sourceField": "内部优先级", "targetField": "internalPriority" },
      { "sourceField": "商家", "targetField": "ticketVender" },
      { "sourceField": "模块", "targetField": "ticketModle" },
      { "sourceField": "创建时间", "targetField": "createTime" },
      { "sourceField": "提单人", "targetField": "reporterName" },
      { "sourceField": "当前负责人", "targetField": "currentAssigneeName" },
      { "sourceField": "1.5负责人", "targetField": "internalOwner" },
      { "sourceField": "记录ID", "targetField": "recordId" }
    ],
    "automation": {
      "autoIdentify": true,
      "autoLogPull": false,
      "autoAiAnalysis": false,
      "autoTranslate": true
    }
  }
}
```

## 风险与说明

- 当前主动拉取仍依赖字段映射正确配置；若缺少“外部工单字段模型”中配置的必填字段，对应记录会转换失败。
- `sortField` 当前仅做配置保留，尚未作为飞书 API 排序参数下发。
- 若定时任务配置了过宽的 `filterFormula` 条件 JSON，虽然有快照去重，但仍会增加无效扫描成本。
