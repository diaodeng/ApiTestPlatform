# 配置任务取证第一期更新（2026-09-21）

## 已实现

- 版本步骤支持显式 `capture_screenshot` 动作，支持 `evidenceType`、`evidenceKey`、`required`、`fullPage`、`maskSelectors`、`waitMs` 等字段。
- 步骤使用稳定 `stepId`；阶段优先保存 `stepIds`，旧 `stepIndexes` 继续兼容。
- 阶段支持 `NONE`、`OPTIONAL`、`REQUIRED`、`BEFORE_AFTER` 取证策略，以及 `WARN`、`BLOCK_ACCEPTANCE`、`BLOCK_RUN` 策略字段。
- Agent 截图先写入受控本地目录并生成 manifest 元数据，再上报 metadata-only `web_run_artifact`；旧 Base64 事件仍保留兼容解析。
- 运行和阶段分别记录业务状态、证据状态和缺失证据摘要。业务成功但证据不完整时不会伪造业务失败；`failure_screenshot` 不满足业务验收证据。
- 阶段事件优先按稳定 `stepId` 关联；旧 Agent 的 1-based 展示索引与历史 0-based 索引均保留明确兼容转换，阶段只有在全部步骤成功/跳过后才成功，重复和乱序事件不会提前结束阶段。
- 阶段终态具备幂等保护，迟到成功/失败事件不会覆盖既有终态；阶段重试清理上一轮结果和时间字段，WRITE 阶段重新回到审批等待；孤儿运行恢复会同步收敛运行阶段并刷新证据状态。

- metadata-only 事件登记前会调用 Agent `file_stat`，重新确认文件存在、未过期且大小和 SHA-256 与上报元数据一致；Agent `file_read` 读取时也会携带 expected 大小/摘要并重新计算当前文件摘要。Agent 离线、文件不存在、过期、被替换或大小/摘要不一致时，资源和产物保留引用但进入不可用状态，不伪造 `READY`/`ONLINE`。
- 新增运行产物受控访问：`GET /configuration-tasks/artifacts/{artifactId}/preview` 与 `/download`。外部只接受 `artifactId`，不把 `resourceId` 或 `objectKey` 当作授权凭证；访问会校验任务/运行/产物/资源归属和元数据一致性，并记录成功/失败访问审计。Agent-local、SFTP、服务端 report 按 Provider 分流读取，读取后再次校验 SHA-256。
- preview 仅允许 PNG、JPEG、WebP、纯文本和 JSON；download 使用安全文件名、流式附件响应和摘要响应头。运行产物列表也增加任务/运行归属校验。

## 当前未实现

- 证据包生成、查询和下载。
- `BLOCK_RUN` 的实际运行阻断和独立验收动作。

## 使用边界

截图正文仍由 Agent 受控目录持有；服务端保存资源索引、校验元数据、运行/阶段/步骤关联和状态摘要。`resourceId` 只是资源身份，不是下载授权；`objectKey` 只是受控相对定位键，也不能作为授权凭证。不得将密码、Cookie、Token、`storageState`、Agent 绝对路径、图片 Base64、ZIP/HTML 正文或任意本地文件路径写入任务模板、普通运行 JSON、普通日志或公开接口契约。

## 验证

- 配置任务回归测试：55 passed。
- 本次涉及模块定向 Ruff：通过。
- Python 编译检查：通过。
- 全量 Ruff 仍包含仓库既有的无关问题，未扩大修复范围。
