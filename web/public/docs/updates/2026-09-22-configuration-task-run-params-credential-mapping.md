# 配置任务运行级参数与系统凭证映射（阶段一）（2026-09-22）

## 新增能力（阶段一）

围绕"版本冻结粒度过严、调试需要反复复制、多系统凭证无法配置"的改进第一批：

1. **运行级步骤参数覆盖**（运行确认弹窗）：
   - **步骤超时(ms)**：默认 10000（单步最长执行时间）；
   - **步骤等待(ms)**：默认 0（每步执行前/后的缓冲等待）；
   - **应用方式**：`作为默认值`（仅对未单独设置超时/等待的步骤生效，与 Agent 既有解析链一致，Agent 零改动）或 `覆盖所有步骤`（下发 `stepTimeoutOverride/stepThinkTimeOverride`，Agent 端将其置于解析链最前，忽略步骤自身配置）；
   - 参数仅作用于本次运行，不写回版本快照。
2. **回写凭证开关**（默认关闭）：开启后运行结束（无论成功失败）会把浏览器最终登录态（结束事件 `runtimeDebug.persistContextFinalState`）回写到版本绑定的统一凭证。回写复用统一凭证域既有服务，安全约束保留：绑定须 `writeback_enabled` 且非 `shared_read` 且启用了本地浏览器状态缓存，否则跳过并记日志；回写失败不影响运行终态。
3. **任务级系统凭证映射**：任务列表新增「凭证映射」操作，维护"系统标识 → 凭证绑定"清单（最多 50 条，批量替换式保存）。映射独立于版本快照，**发布后仍可修改**；后续阶段化执行中阶段将通过 system_key 引用（阶段二）。

## 后端

- 新表 `configuration_task_credential_mapping`（SQL：`server/sql/20260921_configuration_task_credential_mapping.sql`，dev 库已执行）。
- 新服务 `credential_mapping_service.py`（list/save，批量替换式）；路由 `GET/PUT /configuration-tasks/{taskId}/credential-mappings`。
- `TaskRunCreateModel` 新增 `defaultStepTimeoutMs/defaultStepWaitMs/stepParamApplyMode/writebackCredentialEnabled`；`task_run_service` 写入 run_params 并按下发模式组装 runtimeOptions；`handle_agent_run_event` 在 `web_run_finished` 终态后按开关调用 `CredentialWritebackService` 消费事件中的最终 storage_state（失败仅记日志）。

## Agent 端

- `_step_timeout_ms/_step_think_time_ms` 解析链头部新增 `stepTimeoutOverride/stepThinkTimeOverride`（force 模式优先于步骤自身配置）。**客户端需重启生效**。

## 验证

- 配置任务回归测试 16 用例通过；ruff 通过；`npm run build:prod` 通过。
- 浏览器端到端：凭证映射弹窗添加（erp）→ 保存 → 后端落库查询一致；运行弹窗四个新参数区渲染确认（截图）。
- 运行参数的真实执行链路（Agent 端生效）建议在下次真实调试运行时确认：dev 库为真实外部站点，未发起实际运行验证。

## 已知边界

- 强制覆盖模式需要更新并重启客户端（Agent）后才会真正生效；仅"作为默认值"模式在旧客户端上也兼容。
- 回写凭证默认关闭；开启前请确认绑定允许回写，避免覆盖共享登录态。
- 阶段二（多凭证合并初始化、域冲突校验）与阶段三（失败策略、登录失效检测、重试凭证刷新）另行排期。
