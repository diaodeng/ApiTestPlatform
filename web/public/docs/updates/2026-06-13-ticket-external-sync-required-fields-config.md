# 工单外部同步必填字段配置

## 背景

`POST /ticket/sync/external` 会经过 `ticket_controller._normalize_ticket_external_sync_payload` 做入参标准化，外部对接方并不总是一次性满足所有字段要求，因此需要把“必填校验字段”做成可配置项。

## 方案

新增 `ticket.sync.automation.externalSyncRequiredFields` 配置，用于控制外部同步接口当前要强制校验的字段列表。

### 默认字段

当前默认支持并预置以下字段：

- `ticketNo`
- `description`
- `internalPriority`
- `ticketVender`
- `ticketModle`
- `createTime`
- `reporterName`

### 校验规则

- 仅对配置列表中的字段执行非空校验。
- 字段名按原始外部同步入参键匹配。
- 缺失字段时返回 `422`，并提示具体缺失项。

## 影响文件

- `server/modules/ticket/controller/ticket_controller.py`
- `server/modules/ticket/service/ticket_sync_service.py`
- `web/src/views/ticket/syncAutomation/index.vue`

## 页面行为

同步配置页展示当前支持的默认字段，并允许直接录入自定义字段名，保存后写回自动化配置，供后端必填校验读取。
