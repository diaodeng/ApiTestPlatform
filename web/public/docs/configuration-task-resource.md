# 配置任务资源与 Agent 传输

> 当前版本提供资源登记、查询、创建者范围、Agent 本地 manifest、服务端到在线 Agent 的 `begin/chunk/commit` 三段式传输、SFTP 资源上传与下载回传，以及带引用保护的资源删除。Agent 本地文件保存在执行 Agent 受控目录；SFTP 文件保存在远端服务器。

## 功能与入口

资源接口位于 `/configuration-tasks/resources`，需要登录并具备对应资源权限：

- `GET /configuration-tasks/resources`：查询资源元数据列表。
- `GET /configuration-tasks/resources/{resourceId}`：查询资源详情。
- `POST /configuration-tasks/resources`：登记 Agent 本地资源元数据，创建后状态为 `PENDING`。
- `POST /configuration-tasks/resources/{resourceId}/transfers`：创建或复用一次传输，要求资源 Agent 已登记且在线。
- `POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/chunks`：提交一个受限 Base64 分片。
- `POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/commit`：要求 Agent 完成整文件校验，成功后资源才进入 `READY`。
- `POST /configuration-tasks/resources/{resourceId}/ready`：兼容旧入口，但不能绕过 Agent commit 直接就绪。

首期 Provider 仅允许 `agent_local`，服务端不会接收文件内容，也不会把 Agent 绝对路径作为接口参数或响应。资源列表和详情需要登录及对应权限；非管理员只能查看和操作自己登记的资源，管理员可查看全量资源。资源创建还要求 `agentCode` 对应的 Agent 已在系统登记；开始传输时该 Agent 必须在线。

当前 Agent 表只有登记状态，没有项目、商家、租户、部门或 hello credential 字段。因此当前版本不宣称生产级行级 Agent 授权或 Token 认证；资源 ID、transfer ID 和 session ID 也不是下载凭证。

## Agent 本地资源与 Web 上传动作

Agent 本地资源协议使用 `requestType=7` 的小 JSON 控制命令维护受控 manifest，支持开始发布、分片写入、提交校验、元数据查询和过期清理。Web 用例的 `upload_file` 步骤只保存 `fileKey`、资源 ID 和 `multiple`，执行时在 Agent 受控目录内按 manifest 解析文件并调用文件输入框上传。

当前不支持服务端任意路径上传/下载、文件目录浏览、SFTP 真实连接、自动录制本地上传路径，也不允许把 Agent 绝对路径写入步骤参数。


```json
{
  "providerType": "agent_local",
  "providerExecutionSide": "agent",
  "agentCode": "agent-gray04",
  "objectKey": "inputs/price-tag.xlsx",
  "originalFileName": "price-tag.xlsx",
  "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "fileSize": 18342,
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "version": 1,
  "expiresAt": "2026-10-19T00:00:00",
  "remark": "门店价格签输入文件"
}
```

字段说明：

| 字段 | 必填 | 默认值/可选值 | 说明 |
|---|---|---|---|
| `providerType` | 否 | `agent_local` | 首期固定为 Agent 本地 Provider，其他值会被拒绝 |
| `providerExecutionSide` | 否 | `agent` | 首期固定为 Agent 侧访问 |
| `agentCode` | 是 | 无 | 资源所属 Agent 编码 |
| `objectKey` | 是 | 无 | `storage_root` 下的受控相对 key；不能是绝对路径，不能包含 `..` |
| `originalFileName` | 是 | 无 | 展示用原始文件名，不能包含路径分隔符 |
| `mimeType` | 否 | `application/octet-stream` | 文件 MIME 类型 |
| `fileSize` | 是 | 无 | 文件字节数，不能为负数 |
| `sha256` | 是 | 无 | 64 位十六进制 SHA-256，服务端统一保存为小写 |
| `version` | 否 | `1` | 资源版本号，必须大于等于 1 |
| `expiresAt` | 否 | 空 | 资源过期时间；过期后不能确认 ready |
| `remark` | 否 | 空 | 备注 |

## 资源与运行产物的关系

配置任务的输入资源和运行证据都使用 Agent-local 元数据登记，但用途不同：输入资源通过版本的 `inputBindings` 参与运行；截图、日志和报告通过 `task_artifact` 关联运行/阶段。服务端只保存 `resourceId`、Agent、受控 `objectKey`、文件名、MIME、大小、版本和 SHA-256 等元数据，不把 Agent 绝对路径作为契约。

运行证据可使用 `capture_screenshot` 步骤和 `evidenceType`、`evidenceKey` 等字段表达业务语义；旧版 `step_screenshot` 和带 Base64 `data` 的上报仍用于兼容迁移。metadata-only 上报只登记 Agent-local 文件元数据，不等同于服务端已保存文件正文。资源登记成功也不代表页面已有证据 preview 或可下载文件。

当前资源下载接口仍仅针对输入资源 Provider 的既有能力；配置任务运行产物尚未提供专用 preview、download 或 evidence package 接口。不要把资源 ID 当作下载凭证，也不要根据元数据状态推断服务端保存了截图正文。


列表支持 `resourceId`、`agentCode`、`status`、`keyword` 和 `limit`。`status` 可选：`PENDING`、`UPLOADING`、`READY`、`FAILED`、`EXPIRED`、`DELETING`、`DELETED`；`limit` 默认 50，最大 200。

## 传输请求与状态

### 开始传输

`POST /configuration-tasks/resources/{resourceId}/transfers` 请求体可传可选的 `transferId`，用于调用方幂等重试。文件名、大小、SHA-256、版本和 Agent 归属均以资源登记为准，不能由 begin 请求覆盖。服务端返回 `transferId`、`resourceId`、`agentCode`、`sessionId`、状态和接收统计。

### 提交分片

`POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/chunks` 请求体示例：

```json
{
  "index": 0,
  "offset": 0,
  "totalBytes": 18342,
  "chunkBytes": 18342,
  "chunkSha256": "<64位小写SHA-256>",
  "data": "<Base64>"
}
```

单块最大 512 KiB，单文件最大 100 MiB，最多 4096 个分片。服务端会校验 Base64、实际字节数和分片 SHA-256；Agent 对相同分片重复提交返回幂等结果，内容不一致会失败。Base64 正文不写入普通日志或普通响应。

### 提交完成

`POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/commit` 不接收文件正文。Agent 会重新计算完整文件大小和 SHA-256，只有与资源登记值一致时才返回成功；服务端随后将传输置为 `COMPLETED`、资源置为 `READY`。

状态迁移：

```text
资源：PENDING -> UPLOADING -> READY
资源：PENDING/UPLOADING -> FAILED
传输：PENDING -> UPLOADING -> COMPLETED
传输：PENDING/UPLOADING -> FAILED 或 EXPIRED
```

传输默认有 TTL。Agent 断线、session 变化、超时、Agent 拒绝或元数据不一致都会拒绝后续操作并记录脱敏错误；当前版本不支持跨新 session 接管旧传输的断点续传。

## SFTP 资源与下载回传

### SFTP 上传

`POST /configuration-tasks/resources/sftp`：文件正文（受限 Base64，最大 100 MiB）随请求提交，服务端通过统一凭证绑定的 SFTP 连接把文件写入远端（先写 `.part` 再原子 rename），随后登记资源（`providerType=sftp`、`providerExecutionSide=server`，状态直接 `READY`）。

请求体分两部分：资源元数据（`agentCode`、`credentialBindingId`、`objectKey`、`originalFileName` 等）和文件正文（`data`）。`credentialBindingId` 是统一凭证管理中 SFTP 类型凭证的绑定 ID，凭证内容加密保存，接口和日志不回显明文。

远端 `objectKey` 必须是从凭证 `baseDirectory` 出发的受控相对路径，拒绝绝对路径、`..` 穿越和用户目录展开。

### 下载回传

`GET /configuration-tasks/resources/{resourceId}/download`：按 Provider 下载文件内容并 Base64 回传（`providerType=sftp` 走服务端 SFTP 直连；`agent_local` 通过 Agent `file_read` 命令读取受控文件）。下载时重新计算 SHA-256，与登记值不一致则拒绝回传。响应包含元数据和 `data`，不返回任何主机地址或本地路径。

### 删除与引用保护

`POST /configuration-tasks/resources/{resourceId}/delete`：删除资源需走引用保护流程：

1. 资源被运行产物（`task_artifact`）引用时默认拒绝删除，提示先清理相关运行记录；
2. 管理员可 `force: true` 强制删除被引用资源；
3. 删除流程：先置 `DELETING`，再清理远端文件（SFTP 删除远端对象 / Agent `file_delete` 删除受控文件），最后置 `DELETED`；
4. 远端文件清理失败时资源保留在 `DELETING`，可重试；`DELETING/DELETED` 资源不能开始新传输。

## 状态与旧 ready 入口

创建资源后状态为 `PENDING`。旧 `ready` 请求即使提交了匹配的 `fileSize` 和 `sha256`，也不能直接把资源改为 `READY`；必须走在线 Agent 的三段式传输并由 Agent commit 确认。大小或 SHA-256 不匹配会进入 `FAILED`。`DELETING`、`DELETED`、`EXPIRED` 资源不能开始新传输。

## ID 和安全注意事项

- 响应中的 `resourceId` 是字符串，即使数据库使用 BIGINT/Snowflake；前端不能对其调用 `Number()`。
- `resourceId` 只是资源身份，不是下载授权凭证；输入资源可按既有 Provider 下载回传能力读取，运行证据产物仍没有专用下载接口。
- `objectKey` 不是任意本地路径，Agent 应自行在受控根目录中解析。
- 当前接口不代表文件内容已经上传成功；只有 Agent 侧文件实际存在并完成 commit 元数据核对后才可置为 `READY`。
- 当前支持服务端三段式分片传输、SFTP 资源上传、下载回传和带引用保护的删除；不支持跨新 session 接管旧传输的断点续传，短期 transfer token 和完整任务级资源绑定属于后续能力。
