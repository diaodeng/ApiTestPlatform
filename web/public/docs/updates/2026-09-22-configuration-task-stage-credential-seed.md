# 配置任务阶段化执行阶段二：多系统凭证合并初始化（2026-09-22）

## 新增能力

阶段通过"目标系统"声明引用任务凭证映射，运行创建时服务端把各系统凭证的浏览器登录态**按域合并**为单一初始化 seed 下发——一次运行多系统免登录：

1. **阶段"目标系统"声明**：阶段切分弹窗每行新增"目标系统"下拉（选项来自任务的凭证映射清单，可清空）。声明后该阶段执行时使用对应系统凭证的登录态；清空表示沿用版本默认绑定。
2. **多凭证合并初始化**：运行创建时收集本版本所有阶段声明的 system_key → 查任务凭证映射 → 解析各绑定 storageState → 按域合并为单一 `persistContextSeedState` 下发（结构与 Web 用例链路的 runtimeOverrides 语义一致）。
3. **校验规则**：
   - 阶段声明的 system_key 在映射中缺失/未绑定 → 阻断运行，提示具体阶段与系统；
   - 同一 cookie 域 / origin 出现在两个**不同**绑定时视为冲突 → 阻断并列出来源（同一绑定引用多个阶段不算冲突）；
   - 凭证无登录态（未登录过）时跳过该来源，阶段执行时靠手动登录；
   - 版本默认绑定（若有）一并参与合并。
4. **强制刷新登录态**（运行弹窗开关，默认关）：Agent 本地缓存的浏览器状态文件存在时会跳过 seed；开启后强制覆写，用于凭证更新后让新登录态生效。

## 重要修复（本阶段发现）

排查确认：**配置任务链路此前的"版本凭证绑定"只把绑定 ID 透传给 Agent 作调试信息，浏览器登录态初始化（persistContextSeedState）从未真正下发**——此前运行依赖本地状态文件缓存或手动登录。本阶段补齐了这段主链路：单系统（不开合并）场景下仍走版本默认绑定 ID 通道，多系统（阶段声明目标系统）场景走合并 seed。

## 变更清单

- 阶段 DO/运行阶段快照 DO 加 `system_key`（SQL：`server/sql/20260922_configuration_task_stage_system_key.sql`，dev 库已执行）；阶段保存链、定义响应、运行快照透传。
- `task_run_service`：新增 `_merge_stage_credential_seed`（缺失/冲突校验 + 按域合并，凭证解析复用 `CredentialResolveService`）；`_build_run_case_message` 按合并结果下发 `runtimeOptions.runtimeOverrides.persistContextSeedState` 与 `forceRefreshSeedState`。
- `TaskRunCreateModel` 加 `forceRefreshSeedState`；`StageSplitRuleModel` 加 `systemKey`。
- Agent `web_test_service`：`_seed_context_state_file_if_needed` 支持 `forceRefreshSeedState` 强制覆写本地状态文件。
- 前端：`StageEditor.vue` 阶段行"目标系统"下拉（选项取任务凭证映射）；`RunConfirmDialog.vue`"强制刷新登录态"开关。

## 验证

- 回归 16 用例通过；ruff 通过；`build:prod` 通过；dev 库加列完成。
- 浏览器/脚本端到端：阶段 system_key 保存/回读一致（三阶段均 erp）；阶段弹窗"目标系统"下拉回显 erp；映射缺失时合并阻断并列出阶段与系统；为 erp 绑定真实凭证后合并产出 22 cookies/6 域/2 origins；测试草稿 v13 已清理。

## 注意事项

- 使用方式：先在任务「凭证映射」登记系统标识与绑定 → 阶段切分时为相关阶段选"目标系统" → 运行即可多系统免登录；凭证更新直接改映射，运行时开"强制刷新登录态"。
- 同域冲突的两个绑定无法在一次运行共存（浏览器同域 cookie 唯一），系统会阻断并提示；这是浏览器语义决定的。
- 强制刷新登录态开启后，本地缓存的其它站点登录态也会被 seed 覆盖——多系统合并 seed 已包含全部所需系统时无影响。
