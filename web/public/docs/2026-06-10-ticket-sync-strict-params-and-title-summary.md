---
title: 外部工单同步必填与标题总结规则
type: note
source_type: code
created: 2026-06-10
updated: 2026-06-10
---

# 外部工单同步必填与标题总结规则

## 1. `POST /ticket/sync/external` 必填字段

接口只兼容字段的驼峰与下划线写法（例如 `ticketNo` / `ticket_no`），不再做其他猜测映射。

必填字段：

- `ticketNo`
- `description`
- `internalPriority`
- `ticketVender`
- `ticketModle`
- `createTime`
- `reporterName`

缺失任一必填字段时：

- 直接返回 `422`
- 记录告警日志
- 不入库

## 2. 字段转换规则（无猜测）

- `reason` -> `rootCause`（根本原因）
- `ticketVender`：用于匹配所属项目与所属商家（按映射配置关键词做“包含匹配”，外部字段包含任一关键词即命中）
- `ticketModle`：用于匹配所属模块（按模块映射关键词做“包含匹配”，命中后回填模块）
- `ticketStatus`：用于匹配状态（优先状态映射，未命中保留原值）
- `ticketStore`：按“已匹配商家ID + ticketStore(对应 `sap_org_no`)”查询 `ticket_log_pull_store_config`，命中用门店配置，未命中原样保存
- `ticketAssignee`：处理人映射要求完整匹配（不做模糊包含），映射配置支持 `userId` 和 `email`

## 3. `title` 缺省处理

当外部未提供 `title` 时：

1. 优先调用轻量 AI 标题总结；
2. 若 AI 开关关闭、配置缺失或调用失败，则回退为 `description` 前 100 个字符。

## 4. AI 配置中心新增项（轻量 AI）

新增系统参数：

- `ticket.ai.title.summary.enabled`
- `ticket.ai.title.summary.provider.code`
- `ticket.ai.title.summary.prompt.code`

对应在“系统管理 -> AI配置中心 -> 轻量 AI 配置”中维护，形态与工单翻译配置一致。

## 5. 标准请求示例 JSON

### 5.1 驼峰写法（推荐）

```json
{
  "ticketNo": "EXT-20260610-0001",
  "title": "收银端登录失败",
  "description": "华东一区门店反馈收银端登录失败，报错 code=AUTH-401，影响正常开单。",
  "internalPriority": "P1",
  "ticketVender": "京东到家-华东业务线",
  "ticketModle": "POS收银前台",
  "createTime": "2026-06-10 09:30:00",
  "reporterName": "张三",
  "reason": "账号权限配置缺失",
  "ticketStatus": "processing",
  "ticketStore": "SAP310101",
  "ticketAssignee": "lisi",
  "sourceRecordId": "OUTER-REC-10001",
  "sourceRecordUrl": "https://example.com/ticket/OUTER-REC-10001",
  "extraData": {
    "channel": "outer-system-a",
    "traceId": "trace-20260610-0001"
  }
}
```

### 5.2 下划线写法

```json
{
  "ticket_no": "EXT-20260610-0001",
  "title": "收银端登录失败",
  "description": "华东一区门店反馈收银端登录失败，报错 code=AUTH-401，影响正常开单。",
  "internal_priority": "P1",
  "ticket_vender": "京东到家-华东业务线",
  "ticket_modle": "POS收银前台",
  "create_time": "2026-06-10 09:30:00",
  "reporter_name": "张三",
  "reason": "账号权限配置缺失",
  "ticket_status": "processing",
  "ticket_store": "SAP310101",
  "ticket_assignee": "lisi",
  "source_record_id": "OUTER-REC-10001",
  "source_record_url": "https://example.com/ticket/OUTER-REC-10001",
  "extra_data": {
    "channel": "outer-system-a",
    "trace_id": "trace-20260610-0001"
  }
}
```

说明：

- 两种写法不要混用，建议整包统一驼峰或统一下划线；
- 若不传 `title`，系统会按“轻量 AI 总结 -> `description` 前 100 字符”补齐；
- 必填字段缺失会返回 `422`，并记录日志且不入库。

## 6. 同步链路执行模式

- `POST /ticket/sync/external` 先执行主入库链路并快速返回；
- AI 翻译、AI 标题总结、自动化识别/拉日志/分析、群推送在入库成功后后台异步执行；
- 后台 AI 处理异常不会回滚已成功入库的数据，只记录日志并按规则回退。
