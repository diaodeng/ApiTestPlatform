# 配置任务取证第一期更新（2026-09-21）

## 已实现

- 版本步骤支持显式 `capture_screenshot` 动作，支持 `evidenceType`、`evidenceKey`、`required`、`fullPage`、`maskSelectors`、`waitMs` 等字段。
- 步骤使用稳定 `stepId`；阶段优先保存 `stepIds`，旧 `stepIndexes` 继续兼容。
- 阶段支持 `NONE`、`OPTIONAL`、`REQUIRED`、`BEFORE_AFTER` 取证策略，以及 `WARN`、`BLOCK_ACCEPTANCE`、`BLOCK_RUN` 策略字段。
- Agent 截图先写入受控本地目录并生成 manifest 元数据，再上报 metadata-only `web_run_artifact`；旧 Base64 事件仍保留兼容解析。
- 运行和阶段分别记录业务状态、证据状态和缺失证据摘要。业务成功但证据不完整时不会伪造业务失败；`failure_screenshot` 不满足业务验收证据。
- 阶段事件优先按稳定 `stepId` 关联；旧 Agent 的 1-based 展示索引与历史 0-based 索引均保留明确兼容转换，阶段只有在全部步骤成功/跳过后才成功，重复和乱序事件不会提前结束阶段。
- 阶段终态具备幂等保护，迟到成功/失败事件不会覆盖既有终态；阶段重试清理上一轮结果和时间字段，WRITE 阶段重新回到审批等待；孤儿运行恢复会同步收敛运行阶段并刷新证据状态。

- 阶段证据策略的 `requiredTypes` 按“每种类型至少一项”计算，同类型多张截图任意一张即可满足；需要精确指定截图时使用 `requiredEvidenceKeys`。产物引用插入遇到数据库唯一键竞态时会回滚并回查已有引用，避免并发重复登记。

## 当前未实现

- 运行产物专用 preview/download 接口。
- 证据包生成、查询和下载。
- metadata-only 事件登记后的 Agent 文件实时探测和完整的离线、丢失、摘要不匹配取回状态治理。
- `BLOCK_RUN` 的实际运行阻断和独立验收动作。

## 使用边界

截图正文仍由 Agent 受控目录持有；服务端保存资源索引、校验元数据、运行/阶段/步骤关联和状态摘要。`resourceId` 只是资源身份，不是下载授权；`objectKey` 只是受控相对定位键，也不能作为授权凭证。不得将密码、Cookie、Token、`storageState`、Agent 绝对路径、图片 Base64、ZIP/HTML 正文或任意本地文件路径写入任务模板、普通运行 JSON、普通日志或公开接口契约。

## 验证

- 配置任务回归测试：53 passed。
- 本次涉及模块定向 Ruff：通过。
- 全量 Ruff 仍包含仓库既有的无关问题，未扩大修复范围。
