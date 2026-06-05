# AI Provider 管理说明

## 目标
统一管理多个 AI 提供商的接入配置，让工单 AI 分析、协同消息发起 AI、日志拉取后的自动 AI 分析都可以按需选择 Provider 或 Agent。

## 配置入口
- 路径：`系统管理 -> AI Provider管理`
- 菜单权限：`system:aiprovider:list`

## 支持的配置项
- `providerCode`：Provider 编码，作为唯一标识。
- `providerName`：Provider 显示名称。
- `providerType`：Provider 类型，例如 `openai`、`llm`、`azure_openai`、`ollama`、`custom`。
- `agentCode`：绑定的 Agent 编码，可选。
- `modelName`：默认模型名称。
- `providerLevel`：Provider 等级，用于区分优先级或分层管理。
- `baseUrl`：API 基础地址。
- `apiKey`：密钥，服务端加密存储。
- `extraConfig`：扩展环境变量，服务端会在 Worker 执行时一并注入。
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

## 变更说明
- 该能力已经接入工单 AI 分析、消息发起 AI、日志拉取自动 AI 三条链路。
- 后续如果新增流程节点，需要复用同一套 Provider 选择和下发逻辑。
