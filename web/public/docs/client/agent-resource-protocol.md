# Agent 本地资源分片发布与服务端传输

## 已支持范围

新版客户端 Agent 使用独立资源服务保存受控的本地文件资源，不修改 Agent 配置模型。资源索引位于应用数据目录 `storage/data/resource_manifest.json`，完成文件位于 `storage/resources/`，未完成传输位于 `storage/resources/.tmp/`。

服务端通过资源 API 编排三段式传输：先创建资源元数据，再调用 `begin`、逐块调用 `chunk`，最后调用 `commit`。Agent 只接收已登记资源的控制命令，不直接接受任意本地路径。服务端响应只返回传输状态、统计和脱敏错误，不返回文件正文。

命令通过既有 Agent WebSocket request 分片发送，使用 `requestType=7`，服务端响应仍是小 JSON response 分片。文件数据仅放在 `file_chunk.data`，使用 Base64 编码，不会作为普通业务响应返回。

## 服务端编排接口

服务端不让浏览器直接连接 Agent。已登录用户通过资源接口触发下列调用，服务端再使用当前 Agent WebSocket 会话发送 `requestType=7` 控制命令：

```text
POST /configuration-tasks/resources/{resourceId}/transfers
POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/chunks
POST /configuration-tasks/resources/{resourceId}/transfers/{transferId}/commit
```

`begin` 返回并持久化 `transferId` 和 `sessionId`；后续 `chunk`、`commit` 必须来自同一资源、同一 Agent 和同一连接 session。旧连接的迟到响应会被丢弃，不能覆盖新连接或新的传输状态。服务端只有收到 Agent commit 的实际 `size` 和 `sha256` 并与资源元数据匹配，才将资源置为 `READY`。

资源传输接口的最小用户范围是：已登录用户具备传输权限，且资源由该用户创建；管理员可操作全量资源。Agent 必须已登记并在线。当前 `qtr_agent` 没有项目、商家、租户、部门或 hello credential 字段，因此本协议不代表生产级 Token 认证或完整行级授权。

## 控制命令与回执


每条命令都至少包含 `requestType: 7`、`command`。资源 ID和传输 ID只能使用字母、数字、点、下划线和短横线，长度不超过 128。

### 开始发布

```json
{
  "requestType": 7,
  "command": "file_publish_begin",
  "resource_id": "res_demo",
  "transfer_id": "transfer_demo",
  "original_file_name": "demo.txt",
  "mime_type": "text/plain",
  "size": 11,
  "sha256": "<64位小写SHA-256>",
  "version": 1,
  "expires": "2026-09-19T00:00:00Z"
}
```

`size` 不超过 100 MiB；`sha256` 是完整文件 SHA-256。`version` 默认 1，`expires` 留空时默认 24 小时后过期。

### 上传分片

```json
{
  "requestType": 7,
  "command": "file_chunk",
  "transfer_id": "transfer_demo",
  "index": 0,
  "offset": 0,
  "data": "<Base64>",
  "chunk_sha256": "<当前分片SHA-256>"
}
```

单块默认不超过 512 KiB。分片允许乱序；同一 `index`、offset、长度和 hash 的重发会幂等成功，内容不同会失败；分片不能重叠。

### 提交发布

```json
{
  "requestType": 7,
  "command": "file_publish_commit",
  "transfer_id": "transfer_demo"
}
```

只有所有 offset 连续覆盖 `0..size`，且最终大小和 SHA-256 都匹配时才提交。提交过程使用原子 rename，随后写入 manifest。

### 查询元数据

```json
{
  "requestType": 7,
  "command": "file_stat",
  "resource_id": "res_demo"
}
```

响应只包含 resource_id、受控 locator、原始文件名、MIME、大小、SHA-256、版本和生命周期时间，不返回文件正文或绝对路径。

### 清理

```json
{
  "requestType": 7,
  "command": "file_cleanup"
}
```

只清理由本服务登记的过期 `.part` 和 manifest 资源，不接受路径参数，不提供任意删除或目录浏览。

- `file_publish_begin` 成功表示 Agent 已创建或复用临时传输上下文，不表示资源已就绪。
- `file_chunk` 成功表示当前分片已接收或按相同内容幂等确认，不代表完整文件校验通过。
- `file_publish_commit` 成功才表示完整文件已校验、原子 rename 并写入 manifest；响应至少包含实际 `size` 和 `sha256`。
- Agent 失败应返回稳定 `errorCode` 和脱敏 `errorMessage`，不得返回绝对路径、文件正文或凭证。


- locator 只允许 `resources/<resource_id>`；绝对路径、`..`、反斜杠、目录、符号链接逃逸都会拒绝。
- 默认最多同时进行 4 个发布传输；未完成传输 30 分钟无活动后清理；完成资源默认 24 小时过期。
- 错误响应只包含稳定错误码和通用中文消息，不泄露绝对路径。
- 本功能不实现任意文件读取、下载、SFTP 或 AI workspace 文件修改。
