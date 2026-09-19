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
  "triggerType": "manual"
}
```

运行创建时会冻结版本快照和输入资源摘要（版本、大小、SHA-256）。执行复用既有 Web 用例的 `run_case` 协议：输入绑定注入 `runtimeOptions.resourceBindings`，Agent 在受控目录内按资源 ID 解析文件。运行状态为 `PENDING/RUNNING/SUCCESS/FAILED/CANCELLED`；当前为同步执行，HTTP 响应返回最终状态和步骤结果。

运行中步骤的 `upload_file` 参数仍只写 `fileKey`，不写文件路径。

## ID 与注意事项

- 响应中的 `taskId`、`versionId`、`currentVersionId`、`taskRunId` 均为字符串（数据库 BIGINT）；前端不能对其调用 `Number()`。
- 版本发布后不可变；修改任务变量不影响已发布版本，新变量在下一个版本中生效。
- 资源必须通过资源传输接口完成 `begin/chunk/commit` 进入 `READY` 后才能被版本引用。
- 当前不提供：阶段级审批闸门、`PREPARE_WRITE/WRITE` 模式区分、截图/日志产物登记、报告归档、运行取消与恢复、定时触发。生产环境写操作仍需人工确认，不应依赖本接口无人值守执行。
