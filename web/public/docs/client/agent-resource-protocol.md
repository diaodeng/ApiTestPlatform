# Agent 本地资源分片发布

## 已支持范围

新版客户端 Agent 使用独立资源服务保存受控的本地文件资源，不修改 Agent 配置模型。资源索引位于应用数据目录 `storage/data/resource_manifest.json`，完成文件位于 `storage/resources/`，未完成传输位于 `storage/resources/.tmp/`。

命令通过既有 Agent WebSocket request 分片发送，使用 `requestType=7`，服务端响应仍是小 JSON response 分片。文件数据仅放在 `file_chunk.data`，使用 Base64 编码，不会作为普通业务响应返回。

## 命令格式

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

## 安全与限制

- locator 只允许 `resources/<resource_id>`；绝对路径、`..`、反斜杠、目录、符号链接逃逸都会拒绝。
- 默认最多同时进行 4 个发布传输；未完成传输 30 分钟无活动后清理；完成资源默认 24 小时过期。
- 错误响应只包含稳定错误码和通用中文消息，不泄露绝对路径。
- 本功能不实现任意文件读取、下载、SFTP 或 AI workspace 文件修改。
