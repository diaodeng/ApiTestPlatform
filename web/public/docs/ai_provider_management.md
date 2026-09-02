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
- `defaultModel`：默认模型名称。当使用方未指定模型时，系统自动使用此默认模型。
- `providerLevel`：Provider 等级，用于区分优先级或分层管理。
- `baseUrl`：API 基础地址。
- `apiKey`：密钥，服务端加密存储。
- `connectionConfig`：协议连接扩展配置（JSON）。
- `workerEnv`：扩展环境变量，服务端会在 Worker 执行时一并注入。
- `enabled`：是否启用。
- `observabilityEnabled`：是否启用可观测上报，默认关闭。开启后工单 AI 分析会把任务级调用上报到可观测平台。
- `observabilityEndpoint`：OTLP 上报端点基础地址，例如 `https://agents.dmall.com/observe`。
- `observabilityAuthType`：鉴权类型，`bearer`（Agent API Key）或 `basic`（Langfuse `publicKey:secretKey`）。
- `observabilityApiKey`：鉴权密钥明文，服务端加密存储，编辑时留空表示保持不变。
- `observabilityServiceName`：上报的 `service.name`，留空默认 `ticket-ai-analysis`。
- `observabilityCliEnabled`：是否向本机 Codex / Claude Code CLI 注入原生遥测配置，默认关闭。

## 可用模型管理

每个 Provider 可以维护多个可用模型，供使用方按需选择。一个 Provider 对应一个 API 地址和密钥，但可以选择不同的模型（如 `gpt-4o` 做分析、`gpt-4o-mini` 做翻译）。

### 模型管理入口
- 在 Provider 编辑弹窗中，**”可用模型”**表格展示了该 Provider 下所有模型，包含：
  - **模型标识**（model_id）：如 `gpt-4o`、`claude-sonnet-4-20250514`
  - **展示名称**：模型的可读名称
  - **来源**：`远端`（从 API 自动发现）或 `手动`（人工添加）
  - **状态**：启用/禁用
  - **最近发现时间**

### 模型操作
| 操作 | 说明 | 权限 |
|---|---|---|
| 添加模型 | 手动输入模型标识，添加自定义模型 | `system:aiprovider:edit` |
| 从API刷新 | 调用远端 API 拉取最新模型列表并持久化，保留手动添加的模型，标记远端已消失的模型为禁用 | `system:aiprovider:edit` |
| 启用/禁用 | 控制模型是否在使用方页面的下拉选项中可见 | `system:aiprovider:edit` |
| 删除 | 仅支持删除手动添加的模型，远端模型不可删除 | `system:aiprovider:edit` |

### 模型选择规则
1. **默认模型**：Provider 编辑页可设置一个默认模型，使用方未指定模型时自动使用。
2. **使用方覆盖**：工单 AI 分析、同步自动化配置、协同消息等场景，选择 Provider 后可单独选择模型，留空则使用默认模型。
3. **模型下拉来源**：仅显示该 Provider 下已启用的模型，不跨 Provider 混用。

## 生效方式
- 工单 AI 分析弹窗可直接选择 Provider 和模型。
- 协同消息里可以指定 Provider 和模型，后续创建 AI 任务时会沿用。
- 日志拉取配置支持选择 Provider，自动 AI 启用时允许只选 Provider，不再强制只选 Agent。
- 同步自动化配置中，翻译、标题总结、知识提炼、AI 分类、同步提取、汇总通知 AI 解读等各 AI 配置段均支持独立选择 Provider 和模型。
- 如果 Provider 配置了 `agentCode`，前端会自动回填对应 Agent。
- 服务端会把 Provider 解析成 `providerEnv` 下发给 `client_new`，由 Worker 执行时注入环境变量。
- Provider 下发优先级为：当前选中 Provider 的核心连接配置（`apiKey`、`baseUrl`、`defaultModel`） > Provider 的 `workerEnv` 扩展配置 > Agent 工作区中已有的旧配置；因此切换或重试 Provider 时，旧的 Claude Code `.env` 和 Codex Provider 地址会被当前 Provider 覆盖。
- 若 Provider 里配置了模型名称，`client_new` 会把它补到 Worker 命令中作为模型覆盖值。

## 执行规则
- Provider 未启用时，提交任务会直接拒绝。
- Provider 与 Agent 都为空时，不允许启用自动 AI。
- Provider 优先级高于默认系统参数，但仍保留 Agent 兜底逻辑。
- 工单 AI 分析只使用 `ticket_analysis_worker` 用途的 Provider，执行器可选 `codex`（Codex Worker）或 `claude_code`（Claude Code Worker）；发起分析弹窗会按 Provider 的 `supportedExecutors` 收敛可选执行器，并按 `preferredExecutor` 回填默认值。
- Claude Code Worker 以 `claude -p` 非交互模式执行，采用只读权限模式（`plan`）与工具白名单（`Read,Grep,Glob,Bash(rg *)`）保证”只分析不改代码”。
- 模型名称在使用方页面选择后，会透传给协议服务，覆盖 Provider 的默认模型。如果配置段中 `modelName` 为空，则回退使用 Provider 的 `defaultModel`。

## Agent 工单分析并发限制

- 配置入口：`系统管理 -> AI 配置中心 -> Agent 并发数`。
- 配置键：`ticket.ai.agent.maxConcurrentTasks`。
- 默认值：`1`。
- 含义：限制单个 Agent 同时进入工单 AI 分析执行阶段的任务数；超过上限的任务会进入队列等待，不会立即失败。
- 适用范围：工单 AI 分析以及日志拉取后触发的自动工单 AI 分析；不同 Agent 分别计算并发额度。
- 调大并发数前应确认 Agent 主机、Codex/Claude CLI 和 Provider 的限流能力；若任务频繁断连或资源争抢，建议恢复为 `1`。

## Codex Worker 鉴权注意事项
- Agent 会为每次工单 AI 分析创建独立的任务级 Codex 配置目录，不直接修改本机全局 Codex 配置。
- 当执行器为 `codex` 时，Provider 的 `baseUrl` 和 `apiKey` 会同时写入任务级 `config.toml`、`.env` 与 `auth.json`；其中 `config.toml` 的 `experimental_bearer_token` 是 Codex CLI 实际请求的优先认证来源。
- 如果复制的本机 Codex 配置中残留 `experimental_bearer_token = “PROXY_MANAGED”` 或旧令牌，而 Provider 的 `baseUrl` 已切换到远端地址，Worker 可能返回 `401 Unauthorized: Invalid token`，即使同一 API Key 直接访问 Provider 的 `/models` 是正常的。Agent 会在启动 Worker 时覆盖该字段。
- 排查时查看 Agent 任务工作区的 `worker.stderr.txt` 和系统日志中的脱敏 `auth_diagnostic`：`/models` 探测返回 200 表示 API Key/基础地址可用，应继续排查 Responses 接口、模型或 CLI 配置；返回 401 才优先检查 Provider 密钥和权限。日志不会记录 API Key 明文。

## 可观测上报（OTLP）

### 功能说明

在 Provider 上开启"可观测上报"后，该 Provider 的每次工单 AI 分析都会生成一条任务级调用记录，上报到可观测平台（如水滴引擎 `https://agents.dmall.com/observe`）。平台上可以看到：

- **输入（INPUT）**：本次分析发送给 AI 的完整提示词。
- **输出（OUTPUT）**：AI 返回的分析结果 JSON。
- **Token 用量与成本**：按平台配置的模型定价自动计算。
- **会话（Sessions）**：按 `ticket-ai-task-{任务ID}` 聚合，一次分析一个会话。
- **错误与耗时**：失败任务带错误码/错误信息与执行耗时。

### 入口与配置

入口在"系统管理 → AI Provider 管理"的新增/编辑弹窗中，"可观测上报"开关默认关闭。

| 配置项 | 含义 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 可观测上报 | 总开关 | 关闭 | 关闭时以下配置项隐藏但不会清空，重新开启后恢复显示 |
| OTLP端点 | 上报地址 | 无 | 填平台给出的基础地址（如 `https://agents.dmall.com/observe`），系统自动拼接 `/v1/traces`、`/v1/logs` 等子路径 |
| 鉴权类型 | 上报鉴权方式 | `bearer` | `bearer` 填平台生成的 Agent API Key；`basic` 填 Langfuse 集成页的 `publicKey:secretKey`（冒号拼接） |
| 鉴权密钥 | 上报凭据 | 无 | 加密存储，界面脱敏显示；编辑时留空表示保持不变 |
| Service名称 | 平台内的服务名 | `ticket-ai-analysis` | 建议留空使用默认值，便于统一筛选 |
| CLI原生遥测 | 本机 CLI 上报开关 | 关闭 | 开启后，本机 Codex / Claude Code 的执行细节（工具调用、模型请求耗时、CLI 事件日志）也会上报 |

### 上报内容说明

- 任务级上报始终包含：提示词全文、分析结果全文、Token 用量、耗时、模型名、任务/工单 ID、成功或失败状态。
- 失败任务同样会上报，便于在平台统计失败率与错误分布。
- 开启"CLI 原生遥测"后，CLI 自身的 span（工具调用、模型请求）会通过 W3C Trace 上下文挂接到任务链路（Claude Code 支持；Codex 通过相同 `session.id` 关联）。
- 上报失败（如平台不可达）只记录服务端日志，**不会影响 AI 分析任务本身**。

### 示例

以水滴引擎为例：

1. 在平台"集成页"创建集成，得到 Agent API Key。
2. Provider 编辑弹窗中开启"可观测上报"。
3. OTLP端点填 `https://agents.dmall.com/observe`。
4. 鉴权类型选 `Bearer（Agent API Key）`，密钥填平台生成的 Key。
5. 保存后发起一次工单 AI 分析，到平台 Traces 页按 `service.name = ticket-ai-analysis` 筛选即可看到调用记录。

### 注意事项与常见问题

- **网络可达性**：上报由服务端发起；开启"CLI 原生遥测"后，执行 Agent 的那台机器也必须能访问 OTLP 端点。
- **隐私**：提示词与结果全文会上报，如内容敏感请确认平台访问权限。CLI 原生遥测默认不包含提示词原文（CLI 侧保持脱敏默认值）。
- **看不到 CLI 执行细节**：确认"CLI 原生遥测"已开启，且 Agent 已重启加载新配置。
- **平台上 Sessions 页没有任务会话**：会话按 `ticket-ai-task-{任务ID}` 聚合，确认筛选时间范围覆盖任务执行时间。
- **Token 消耗图表为 0 但 span 有 Token**：平台的按分钟聚合图表依赖平台侧映射，任务级 Token 数值以任务详情为准。

## 变更说明
- 该能力已经接入工单 AI 分析、消息发起 AI、日志拉取自动 AI 三条链路。
- 后续如果新增流程节点，需要复用同一套 Provider 选择和下发逻辑。
- AI Provider 的角色权限现在已补齐目录和按钮级权限，启动时会自动同步到系统菜单表，角色权限设置页面可以直接勾选对应权限码。
- 支持一个 Provider 配置多个可用模型，使用方可按场景选择不同模型，实现”同一 API Key 不同模型”的灵活配置。
- 新增 Provider 级可观测上报配置（OTLP）：工单 AI 分析任务级调用（输入/输出/Token/耗时）上报可观测平台，可选开启本机 CLI 原生遥测。详见"可观测上报（OTLP）"章节。
