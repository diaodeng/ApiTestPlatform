# AI Provider 管理说明

## 目标
统一管理多个 AI 提供商的接入配置，让工单 AI 分析、协同消息发起 AI、日志拉取后的自动 AI 分析都可以按需选择 Provider 或 Agent。

## 配置入口
- 路径：`系统管理 -> AI Provider管理`
- 菜单权限：`system:aiprovider:list`
- 按钮权限：
  - `system:aiprovider:query`：查看详情
  - `system:aiprovider:add`：新增
  - `system:aiprovider:edit`：修改
  - `system:aiprovider:remove`：删除

## 支持的配置项
- `providerCode`：Provider 编码，作为唯一标识。
- `providerName`：Provider 显示名称。
- `platformCode`：所属平台，例如 `openai`、`openai_compatible`、`azure_openai`、`anthropic`、`ollama`、`custom`。
- `apiProtocol`：API 调用协议，例如 `openai_chat_completions`、`anthropic_messages`。
- `supportedUsages`：允许的业务用途，例如工单轻量AI、工单AI分析、工单向量化、模型目录发现。
- `supportedExecutors`：兼容的执行器，例如服务端直连、Codex Worker、Claude Code Worker。
- `preferredExecutor`：默认执行器。当 Provider 的兼容执行器同时包含多个工单分析执行器（Codex / Claude Code）时，用于确定发起工单 AI 分析时的默认执行器；留空时默认取首个兼容执行器。
- `preferredAgentCode`：首选 Agent 编码，可选，用于分析任务默认回填对应 Agent。
- `defaultModel`：默认模型名称。
- `providerLevel`：Provider 等级，用于区分优先级或分层管理。
- `baseUrl`：API 基础地址。
- `apiKey`：密钥，服务端加密存储。
- `connectionConfig`：协议连接扩展配置（JSON）。
- `workerEnv`：扩展环境变量，服务端会在 Worker 执行时一并注入。
- `enabled`：是否启用。

## 生效方式
- 工单 AI 分析弹窗可直接选择 Provider。
- 协同消息里可以指定 Provider，后续创建 AI 任务时会沿用。
- 日志拉取配置支持选择 Provider，自动 AI 启用时允许只选 Provider，不再强制只选 Agent。
- 如果 Provider 配置了 `agentCode`，前端会自动回填对应 Agent。
- 服务端会把 Provider 解析成 `providerEnv` 下发给 `client_new`，由 Worker 执行时注入环境变量。
- 若 Provider 里配置了模型名称，`client_new` 会把它补到 Worker 命令中作为模型覆盖值。

## 执行规则
- Provider 未启用时，提交任务会直接拒绝。
- Provider 与 Agent 都为空时，不允许启用自动 AI。
- Provider 优先级高于默认系统参数，但仍保留 Agent 兜底逻辑。
- 工单 AI 分析只使用 `ticket_analysis_worker` 用途的 Provider，执行器可选 `codex`（Codex Worker）或 `claude_code`（Claude Code Worker）；发起分析弹窗会按 Provider 的 `supportedExecutors` 收敛可选执行器，并按 `preferredExecutor` 回填默认值。
- Claude Code Worker 以 `claude -p` 非交互模式执行，采用只读权限模式（`plan`）与工具白名单（`Read,Grep,Glob,Bash(rg *)`）保证“只分析不改代码”。

## 变更说明
- 该能力已经接入工单 AI 分析、消息发起 AI、日志拉取自动 AI 三条链路。
- 后续如果新增流程节点，需要复用同一套 Provider 选择和下发逻辑。
- AI Provider 的角色权限现在已补齐目录和按钮级权限，启动时会自动同步到系统菜单表，角色权限设置页面可以直接勾选对应权限码。
