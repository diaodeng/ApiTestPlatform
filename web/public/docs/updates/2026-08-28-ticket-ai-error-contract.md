---
title: 工单 AI Worker 失败错误码与真实异常透传
---

# 工单 AI Worker 失败错误码与真实异常透传

## 变更内容

- Worker 失败响应新增 `errorCode`、`errorMessage` 和 `workerExitCode`。
- 失败响应不再携带工单正文、分析结果或工作区结果元数据。
- Agent 网关区分“传输成功”和“Worker 业务成功”，不再用“操作成功”覆盖内层异常。
- 服务端只依据结构化 `success/status/errorCode/errorMessage` 更新任务和审计记录，不再从工单正文匹配异常。
- `PermissionDenied` 等本地诊断信息作为告警记录；若同时存在 Provider 配额耗尽，则以配额错误作为主错误。

## 错误码示例

- `AI_PROVIDER_QUOTA_EXCEEDED`：Provider Token 或配额耗尽。
- `AI_PROVIDER_AUTH_FAILED`：Provider 鉴权失败。
- `AI_WORKER_PERMISSION_DENIED`：Worker 本地权限异常。
- `AI_WORKER_TIMEOUT`：Worker 执行超时。
- `AI_WORKER_RESULT_INVALID`：Worker 未返回符合要求的结果。
- `AI_TICKET_NOT_FOUND` / `AI_REPO_MAPPING_NOT_FOUND`：任务关联的工单或仓库映射不存在。
- `AI_AGENT_NOT_AVAILABLE`：没有可用的本地 Agent。
- `AI_TASK_INTERRUPTED`：服务重启时任务尚未完成。

本次只调整错误传递和落库契约，没有调整 `digest/full_directory/hybrid` 的日志读取策略。
