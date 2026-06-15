# 工单日志拉取重新拉取参数恢复修复

## 背景

工单详情页或日志拉取记录页点击“重新拉取”时，部分历史记录会提示“当前记录缺少可重新拉取的原始参数”。

后端重拉接口只接收记录 ID，会在服务端根据历史 `ticket_log_pull_record.command_content` 和记录字段恢复 `TicketLogPullCreateModel`。旧记录可能存在 `command_content` 为空、字符串化、字段使用下划线命名，或未配置日志截取时间范围的情况。

## 本次调整

- 重新拉取恢复参数时兼容 `command_content` 为 JSON 字符串或字典。
- 兼容 `modifyTime/modify_time`、`timeRangeMode/time_range_mode`、`logBeginTime/log_begin_time`、`logEndTime/log_end_time` 等字段名差异。
- `fileMaxSize/zipMaxSize` 使用安全正整数解析，历史脏值会回退到默认 500。
- 未配置日志截取时间范围的历史记录不再显式传入空 `logBeginTime/logEndTime`，避免被模型误判为“开始/结束时间填写不完整”。
- 仍保留必要校验：如果历史记录无法恢复 `modifyTime` 或 `path`，继续返回“当前记录缺少可重新拉取的原始参数”，避免提交不完整外部命令。

## 影响范围

- 后端：`server/modules/ticket/service/ticket_log_pull_service.py`
- 前端：无需调整，继续通过记录 ID 调用重新拉取接口。

## 使用说明

新建日志拉取记录仍会保存前端原始入参，重新拉取优先使用原始参数恢复。历史记录只要保留了 `modifyTime` 或 `path`，并且记录自身有 `vendorId/storeId/posNo/commandDataType/storageMode`，即可重新提交。
