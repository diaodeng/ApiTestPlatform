# 配置任务管理

> 配置任务用于把“按商家、门店执行一组网页操作 SOP 并绑定输入文件”的实施工作结构化。当前提供任务定义、版本快照、输入资源绑定和运行执行；阶段审批、截图产物和报告归档尚未提供。

## 功能与入口

任务接口位于 `/configuration-tasks`，需要登录并具备对应权限：

- `GET /configuration-tasks`：查询任务列表，支持 `keyword` 和 `limit`。
- `POST /configuration-tasks`：创建任务，需提供 `taskName`、`agentCode` 和可选 `variables`。
- `GET /configuration-tasks/{taskId}`：任务详情。
- `PUT /configuration-tasks/{taskId}`：更新任务名称、描述、Agent、变量或状态。
- `POST /configuration-tasks/{taskId}/versions`：创建版本草稿（`DRAFT`）。
- `GET /configuration-tasks/{taskId}/versions`：版本列表。
- `GET /configuration-tasks/versions/{versionId}`：版本详情。
- `PUT /configuration-tasks/versions/{versionId}`：更新版本草稿。
- `POST /configuration-tasks/versions/{versionId}/publish`：发布版本。
- `POST /configuration-tasks/{taskId}/runs`：创建运行并同步执行。
- `POST /configuration-tasks/runs/{taskRunId}/stop`：停止或取消运行。
- `GET /configuration-tasks/{taskId}/runs`：运行列表。
- `GET /configuration-tasks/runs/{taskRunId}`：运行详情。

权限码包括 `configuration_task:task:list/query/add/edit/publish/run`。

## 版本与输入绑定

版本草稿包含 `startUrl`、`browserName`、`headless`、`credentialBindingId`、`variables`、`steps` 和 `inputBindings`：

```json
{
  "startUrl": "https://test.example.com/store",
  "browserName": "chromium",
  "headless": true,
  "inputBindings": {
    "price_tag": ["900000000000001"]
  }
}
```

- `inputBindings` 的键是步骤里 `upload_file` 使用的 `fileKey`，值是资源 ID 字符串数组，每个键最多绑定 20 个资源；
- 已发布版本不可修改；重新执行请创建新版本草稿并发布；
- 发布时服务端校验：至少一个启用步骤；每个绑定资源存在、状态 `READY`、且资源所属 Agent 与任务执行 Agent 一致。

## 运行执行

`POST /configuration-tasks/{taskId}/runs` 默认使用任务当前发布版本，也可用 `versionNo` 指定历史版本：

```json
{
  "agentCode": "agent-gray04",
  "versionNo": 3,
  "triggerType": "manual",
  "manualLoginEnabled": false,
  "manualLoginWaitSec": 120,
  "timeoutSeconds": 1800
}
```

运行创建时会冻结版本快照和输入资源摘要（版本、大小、SHA-256）。执行复用既有 Web 用例的 `run_case` 协议：输入绑定注入 `runtimeOptions.resourceBindings`，Agent 在受控目录内按资源 ID 解析文件。运行状态为 `PENDING/RUNNING/SUCCESS/FAILED/CANCELLED`；当前为同步执行，HTTP 响应返回最终状态和步骤结果，执行过程中的步骤进度会通过 Agent 事件实时写入运行记录，可随时通过运行详情查看。

运行控制与限制：

- **并发租约**：同一 Agent 同时只允许一个运行中的配置任务；存在未完成运行时新运行会被拒绝，需要等待完成或先停止。
- **手动登录**：`manualLoginEnabled` 为 `true` 时先打开浏览器等待人工登录（等待 `manualLoginWaitSec` 秒），登录完成后自动继续执行步骤；适合需要扫码或验证码的页面。
- **超时**：`timeoutSeconds` 默认 1800 秒，可按任务时长调整（30–21600 秒）。
- **停止**：`POST /configuration-tasks/runs/{taskRunId}/stop` 向 Agent 发送停止命令并把运行收敛为 `CANCELLED`；Agent 离线时本地状态仍会收敛，保证取消幂等。
- **孤儿恢复**：服务重启或 Agent 断线导致运行长期无进展时，恢复任务（建议 10 分钟周期，阈值 60 分钟）会把它收敛为 `FAILED`（错误码 `RUN_ORPHAN_RECOVERED`），可重新发起运行。
- **资源过期清理**：清理任务（建议每小时周期）把超过保留期的资源收敛为 `EXPIRED`、超时未完成的传输收敛为 `EXPIRED`；资源过期后不能被新版本引用，历史运行按快照不受影响。

两个维护任务需要在「系统监控 → 定时任务」中创建：`module_task.scheduler_maintenance.cleanup_configuration_task_resources` 和 `module_task.scheduler_maintenance.recover_configuration_task_runs`。

运行中步骤的 `upload_file` 参数仍只写 `fileKey`，不写文件路径。

## ID 与注意事项

- 响应中的 `taskId`、`versionId`、`currentVersionId`、`taskRunId` 均为字符串（数据库 BIGINT）；前端不能对其调用 `Number()`。
- 版本发布后不可变；修改任务变量不影响已发布版本，新变量在下一个版本中生效。
- 资源必须通过资源传输接口完成 `begin/chunk/commit` 进入 `READY` 后才能被版本引用。
- 当前不提供：阶段级审批闸门、`PREPARE_WRITE/WRITE` 模式区分、截图/日志产物登记、报告归档、定时触发运行。生产环境写操作仍需人工确认，不应依赖本接口无人值守执行。
