# 配置任务管理

> 配置任务用于把“按商家、门店执行一组网页操作 SOP 并绑定输入文件”的实施工作结构化。当前提供任务定义、版本快照、输入资源绑定、运行执行、阶段审批闸门、截图产物登记和报告归档（Word 兼容文件 + 飞书通知）。

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
- `POST /configuration-tasks/versions/{versionId}/stages`：保存版本阶段切分（仅草稿）。
- `GET /configuration-tasks/versions/{versionId}/stages`：查询版本阶段定义。
- `GET /configuration-tasks/runs/{taskRunId}/stages`：查询运行阶段列表。
- `POST /configuration-tasks/runs/stages/{runStageId}/approve`：审批 WRITE 阶段（通过/拒绝）。
- `POST /configuration-tasks/runs/stages/{runStageId}/retry`：重试失败阶段。
- `GET /configuration-tasks/runs/{taskRunId}/artifacts`：查询运行产物列表。
- `POST /configuration-tasks/runs/artifacts/agent-report`：Agent 上报步骤截图/日志（供客户端集成）。
- `POST /configuration-tasks/runs/{taskRunId}/report`：生成并归档运行报告，`notifyFeishu=true` 时推送飞书通知。
- `POST /configuration-tasks/templates/from-recording`：录制会话转任务版本草稿（录制→模板转换器）。
- `GET /configuration-tasks/{taskId}/schedule`：查询定时触发配置。
- `PUT /configuration-tasks/{taskId}/schedule`：保存定时触发配置（cron 5 字段表达式）。

权限码包括 `configuration_task:task:list/query/add/edit/publish/run/approve`、`configuration_task:artifact:upload`、`configuration_task:report:generate`。

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

## 阶段与审批闸门

版本草稿支持把步骤切分为阶段（最多 20 个），每个阶段声明模式：

| 模式 | 用途 | 执行策略 |
|---|---|---|
| `READ` | 查询、核对 | 自动执行 |
| `PREPARE_WRITE` | 打开并填写待提交值 | 自动执行 |
| `WRITE` | 保存、导入、状态变更 | 执行前必须审批 |
| `VERIFY` | 修改后重新查询 | 自动执行 |

阶段切分请求示例：

```json
[
  { "stageKey": "query", "stageName": "查询现状", "mode": "READ", "stepIndexes": [0, 1] },
  { "stageKey": "save", "stageName": "提交配置", "mode": "WRITE", "stepIndexes": [2] }
]
```

- 运行创建时阶段快照到运行记录；`WRITE` 阶段创建即进入 `WAITING_APPROVAL`，审批通过后才允许执行；
- 审批拒绝会取消整个运行（错误码 `STAGE_REJECTED`）；
- 任一阶段失败会自动跳过后续阶段；失败阶段可重试，`WRITE` 阶段重试必须重新审批；
- 未声明阶段时按单一全量阶段执行，保持向后兼容。

## 产物登记

Agent 执行失败步骤时自动截图，并通过事件上报到服务端；服务端把截图登记为 Agent 本地受控资源（状态 `READY`）并建立产物引用（`task_artifact`）。产物类型包括 `step_screenshot`、`failure_screenshot`、`execution_log`、`report`。产物只保存资源引用和元数据，不把图片 Base64 写入运行记录或报告正文。同一截图重复上报幂等返回同一资源。

## 录制转模板

在任务列表点「录制转模板」，填写录制记录 ID 并标记变量/上传 fileKey，即可把既有 Web 录制转成任务版本草稿：

- 变量标记 `{"0": "store.id"}`：把第 1 步（fill/select）的输入值替换为 `${store.id}` 占位符，运行时由版本变量注入；
- 上传标记 `{"3": "price_tag"}`：把第 4 步上传动作的 fileKey 标注为 `price_tag`，配合版本输入绑定使用；
- 转换生成 DRAFT 版本，需在版本编辑器中检查后发布。

## 定时触发运行

任务的「定时」配置支持 5 字段 cron（本地时区）：`0 9 * * *` 每天 9 点、`0 9 * * 1-5` 工作日 9 点、`*/30 * * * *` 每 30 分钟。

- 可指定执行版本号和 Agent（缺省使用任务当前发布版本和默认 Agent）；
- 保存配置后需在「系统监控 → 定时任务」创建任务：调用目标 `module_task.scheduler_configuration.trigger_configuration_task_run`，参数 `{"task_id": 任务ID}`，cron 与配置一致；
- 定时触发的运行 `triggerType=scheduled`，同样受并发租约、审批闸门和超时约束；
- 未启用定时或任务配置缺失时调度自动跳过，不做任何写操作。

## 报告归档

`POST /configuration-tasks/runs/{taskRunId}/report?notifyFeishu=true` 生成运行报告并归档：

- 报告文件为 Word 兼容 HTML（`.doc`），Word/WPS 可直接打开另存为 `.docx`，无需额外依赖；
- 报告内容：运行信息、阶段执行结果、产物清单（文件名 + 资源 ID）；
- 报告文件保存在服务端 `storage/configuration-task-reports/`，登记为资源并关联产物引用；
- `notifyFeishu=true` 时推送飞书机器人通知（使用系统统一飞书配置），推送失败不影响归档。


## ID 与注意事项

- 响应中的 `taskId`、`versionId`、`currentVersionId`、`taskRunId` 均为字符串（数据库 BIGINT）；前端不能对其调用 `Number()`。
- 版本发布后不可变；修改任务变量不影响已发布版本，新变量在下一个版本中生效。
- 资源必须通过资源传输接口完成 `begin/chunk/commit` 进入 `READY` 后才能被版本引用。
- 当前不提供：定时触发运行、批量门店编排、运行中 Web 界面实时进度推送（可通过运行详情轮询查看）。生产环境 `WRITE` 阶段已默认强制审批闸门，请勿为审批账号开通无人值守的自动审批。
