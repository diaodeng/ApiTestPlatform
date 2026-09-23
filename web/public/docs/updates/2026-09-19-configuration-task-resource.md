# 配置任务资源与 Agent 传输切片

## 变更

- 新增 `configuration_task_resource_object` 资源元数据表及 Snowflake BIGINT 主键；新增 `(agent_code, object_key, version)` 唯一约束，重复登记返回同一资源身份。
- 新增资源创建、查询、详情和资源传输 API：`begin/chunk/commit`。服务端保存 `transfer_id`、资源元数据、Agent 编码、WebSocket `session_id`、接收统计和错误审计，不保存文件正文。
- 资源状态由 Agent commit 的实际大小和 SHA-256 确认后才从 `UPLOADING` 进入 `READY`；旧 `ready` 入口仅兼容保留，不能绕过 Agent commit。传输失败或过期会记录稳定错误并收敛资源状态。
- 首期 Provider 固定为 `agent_local`。文件最终保存在 Agent 受控目录，Agent 使用 manifest、`.part` 临时文件和原子 rename；资源响应的 `resourceId` 统一序列化为字符串。
- 服务端传输要求 Agent 已登记且在线，传输操作按资源创建者范围限制，管理员可查看全量；连接 session 变化时拒绝迟到分片和 commit。

## 边界

当前切片不提供 SFTP、下载回传、任意路径读写、任务版本/运行实例/输入绑定、截图和 Word/飞书报告归档，也不提供生产级 hello credential、短期 Token 或跨新 session 的断点续传接管。Web `upload_file` 仅完成动作参数标准化和 Agent 本地受控文件定位，完整配置任务运行域仍需后续实现。

## 验证

- 服务端资源和传输测试覆盖资源创建者范围、登记 Agent 校验、传输状态迁移、重复 begin/commit、分片大小与摘要校验、commit 元数据不匹配和传输过期。
- Agent 测试覆盖受控 locator、manifest 原子写入、乱序/重复分片、commit 完整校验和资源命令日志脱敏。
- 连接会话专项测试和前端生产构建作为本阶段最终验证项执行，未通过前不宣称真实 Agent 端到端联调完成。
