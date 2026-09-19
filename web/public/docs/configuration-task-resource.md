# 配置任务资源元数据接口

> 当前版本提供资源身份、元数据、Agent 本地受控 manifest 和资源就绪确认；服务端资源接口本身不接收文件内容。Agent 本地分片发布协议和 Web `upload_file` 动作已提供最小可验证子集，服务端到 Agent 的完整传输编排、SFTP 和任务级资源绑定仍未上线。

## 功能与入口

资源接口位于 `/configuration-tasks/resources`，需要登录并具备对应资源权限：

- `GET /configuration-tasks/resources`：查询资源元数据列表。
- `GET /configuration-tasks/resources/{resourceId}`：查询资源详情。
- `POST /configuration-tasks/resources`：登记 Agent 本地资源元数据，创建后状态为 `PENDING`。
- `POST /configuration-tasks/resources/{resourceId}/ready`：由调用方提交 Agent 实际文件大小和 SHA-256，匹配登记值后变为 `READY`。

首期 Provider 仅允许 `agent_local`，服务端不会接收文件内容，也不会把 Agent 绝对路径作为接口参数或响应。

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

## 查询参数

列表支持 `resourceId`、`agentCode`、`status`、`keyword` 和 `limit`。`status` 可选：`PENDING`、`UPLOADING`、`READY`、`FAILED`、`EXPIRED`、`DELETING`、`DELETED`；`limit` 默认 50，最大 200。

## 状态与 ready

创建后资源状态为 `PENDING`。调用 `ready` 时提交：

```json
{
  "fileSize": 18342,
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "version": 1
}
```

大小和 SHA-256 均匹配时状态变为 `READY`；任一不匹配时状态变为 `FAILED`。`DELETING`、`DELETED`、`EXPIRED` 资源不能再次确认 ready。

## ID 和安全注意事项

- 响应中的 `resourceId` 是字符串，即使数据库使用 BIGINT/Snowflake；前端不能对其调用 `Number()`。
- `resourceId` 只是资源身份，不是下载授权凭证。
- `objectKey` 不是任意本地路径，Agent 应自行在受控根目录中解析。
- 当前接口不代表文件内容已经上传成功；只有 Agent 侧文件实际存在并完成元数据核对后才可置为 `READY`。
- 文件分片、断点续传、短期 transfer token 和 SFTP Provider 属于后续能力，当前版本不会伪造这些接口。
