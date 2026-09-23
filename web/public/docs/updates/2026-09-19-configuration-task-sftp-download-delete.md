# 配置任务 SFTP 资源、下载回传与删除保护切片

## 变更

- 新增 `modules/configuration_task/util/sftp_provider.py`：paramiko SFTP Provider，支持 upload（.part + 原子 rename + 失败清理）、download、stat、delete；object key 校验拒绝绝对路径/穿越/用户目录展开；连接与操作有独立超时。
- 凭证链路：SFTP 连接配置来自统一凭证绑定（`auth_credential_binding`），密文运行时解密；绑定 ID 以 `SFTP_UPLOAD|bindingId=x` 格式写入资源审计摘要，供下载/删除时重新解析凭证；凭证明文不出现在接口、日志或资源记录。
- 资源上传：`POST /configuration-tasks/resources/sftp`，正文受限 Base64（≤100 MiB），远端写入成功后登记 `providerType=sftp / providerExecutionSide=server / status=READY` 资源；唯一身份冲突幂等返回已有资源。
- 下载回传：`GET /configuration-tasks/resources/{id}/download`——SFTP 资源服务端直连下载；agent_local 资源经 Agent 新增 `file_read` 命令（requestType=7）读取受控文件；两种路径回传前都重新计算 SHA-256 并与登记值比对，不一致拒绝。
- 删除保护：`POST /configuration-tasks/resources/{id}/delete`——被 `task_artifact` 引用时默认拒绝（管理员 `force` 可强制）；状态机 `DELETING → DELETED`，先标记再清理远端文件（SFTP delete / Agent `file_delete`），清理失败保留 `DELETING` 可重试。
- Agent 端：`file_read`（Base64 回传受控资源，限 manifest 内资源与单文件上限）、`file_delete`（删除受控文件与 manifest 条目，幂等）；两命令均受既有受控 locator 校验约束。
- 新增权限码：`configuration_task:resource:sftp`、`configuration_task:resource:download`、`configuration_task:resource:delete`。

## 边界

- SFTP host key 当前使用 AutoAdd 策略（首期内网场景），known_hosts 严格校验为后续加固；
- 下载回传为整文件 Base64，不适合超大文件流式下载；分块下载属后续能力；
- `agent_local` 资源删除要求目标 Agent 在线；Agent 离线时删除会失败并保留 `DELETING`，可等 Agent 恢复后重试；
- 凭证绑定 ID 存于审计摘要文本（受控格式），凭证模型后续若增加专用扩展字段可平滑迁移。

## 验证

- 新增 9 项测试：object key 校验、上传 .part/rename 时序（mock SFTP）、下载 SHA-256 校验、非 READY 拒绝下载、引用保护拒绝/管理员强制、DELETING→DELETED 流程、清理失败保留 DELETING、Agent file_read 下载与摘要不一致拒绝；全量相关 45 项测试通过。
- Ruff、Python 编译、前端生产构建通过；真实 SFTP 服务器与 Agent 端到端联调待执行。
