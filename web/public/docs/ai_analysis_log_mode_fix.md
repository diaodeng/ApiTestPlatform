# AI 分析日志模式修复记录

## 日期
2026-07-07

## 问题描述
用户在前端选择"摘要+完整目录"（hybrid）模式进行 AI 分析，但 agent（codex exec）总是显示"已读取 context.json，确认本次应采用 digest 模式分析"，导致分析不准确。

## 根因分析

### 数据流问题
1. **任务创建时**（server/modules/ticket/service/ai/ticket_ai_analysis_service.py:1853）：
   - 调用 _build_context_payload(db, ticket, mapping, log_record, request) 构建完整上下文
   - equest 参数包含用户选择的 log_analysis_mode（如 "hybrid"）
   - 正确设置 context_payload["logAnalysisMode"] = "hybrid"

2. **任务执行时**（server/modules/ticket/service/ai/ticket_ai_analysis_service.py:2365）：
   - 调用 _load_workspace_context_payload(db, task, ticket, mapping, workspace_dir)
   - 如果 context.json 不存在（首次执行），调用 _build_context_payload(db, ticket, mapping, log_record) **没有传递 request 参数**
   - 导致 _resolve_log_analysis_options 使用系统默认值 "digest" 而不是用户选择的值

3. **紧凑快照补充逻辑问题**（原代码 line 1225-1244）：
   - 代码尝试从 	ask.analysis_context（紧凑快照）补充缺失字段
   - 但条件是 if key not in context_payload or context_payload.get(key) in (None, "", {})
   - 由于 _build_context_payload 已设置 logAnalysisMode="digest"，条件为 False
   - 紧凑快照中的正确值（"hybrid"）不会覆盖默认值

### Prompt 指令问题
- 原 prompt 只说"日志读取策略由 context.json 中的 logAnalysisMode 决定"
- 但没有在 prompt 文本中直接告知 agent 当前模式是什么
- Agent 需要额外读取 context.json 才能知道模式，增加了出错概率

## 修复方案

### 1. 修复上下文加载逻辑（server/modules/ticket/service/ai/ticket_ai_analysis_service.py:1225-1254）
将配置项分为两类：
- **用户配置项**（logAnalysisMode, forceRefresh, selectedAgentCode 等）：始终优先使用紧凑快照中的值，因为这些代表用户提交时的原始选择
- **其他配置项**（sourceLogPullRecordId 等）：仅在缺失时从快照补充

`python
# 用户配置项：始终优先使用紧凑快照中的值
user_config_keys = (
    "logAnalysisMode",
    "logWindowMissingStrategy",
    "logRequestedBeginTime",
    "logRequestedEndTime",
    "forceRefresh",
    "extraInstruction",
    "selectedAgentCode",
    "selectedAiProviderCode",
    "selectedAiProviderName",
    "selectedAiProviderType",
    "selectedWorkerModel",
)
for key in user_config_keys:
    compact_val = compact_context.get(key)
    if compact_val not in (None, "", {}):
        context_payload[key] = compact_val
`

### 2. 强化 Prompt 指令
修改 _build_prompt 方法，增加 log_analysis_mode 参数，并在 prompt 文本中直接告知 agent 当前模式：

`python
def _build_prompt(
    cls,
    workspace_path: str,
    mapping: TicketAiRepoMapping,
    ticket: Ticket,
    *,
    prompt_layers: dict[str, Any] | None = None,
    prompt_templates: list[dict[str, Any]] | None = None,
    extra_instruction: str = "",
    log_analysis_mode: str = "digest",  # 新增参数
) -> str:
`

Prompt 文本改为：
`
3. **本次日志分析模式为 {log_analysis_mode}**（已写入 context.json 的 logAnalysisMode 字段）：
   - digest：优先阅读 logs_ai_digest.txt...
   - ull_directory：不要依赖摘要...
   - hybrid：先阅读摘要，再使用 source_logs/ 完整目录复核关键证据。
   **请严格按照上述模式执行，不要自行切换为其他模式。**
`

### 3. 同步修改 client_new 端
client_new/services/ticket_ai_analysis_service.py 中的 _build_prompt 方法也做了相同修改。

## 关于 codex exec 的说明

用户问："codex exec 会自己多次分析日志多次请求AI接口进行总结吗？"

**答案：不会。**

- codex exec 是单次执行模式，每次执行只发起 **一次 AI API 调用**
- 在这次调用中，AI 可以使用工具（读文件、运行命令等）收集信息
- 所有工具调用都在同一次 AI 推理循环中完成，不会额外发起 API 请求
- 这与 codex（交互模式）不同，交互模式可以多轮对话

因此，使用 codex exec 执行分析时：
- API 成本：每次任务 1 次 AI 调用
- 工具调用：AI 可以根据需要读取多个文件、运行多个命令
- 执行时间：取决于 AI 的工具调用次数和复杂度

## 修改文件
1. server/modules/ticket/service/ai/ticket_ai_analysis_service.py
   - _load_workspace_context_payload: 修复用户配置项的优先级逻辑
   - _build_prompt: 增加 log_analysis_mode 参数，强化 prompt 指令
   - 两处调用 _build_prompt 的地方传入 log_analysis_mode

2. client_new/services/ticket_ai_analysis_service.py
   - _build_prompt: 增加 log_analysis_mode 参数，强化 prompt 指令
   - 调用处传入 log_analysis_mode

## 验证建议
1. 创建新的 AI 分析任务，选择 "hybrid" 模式
2. 检查生成的 context.json 是否包含 "logAnalysisMode": "hybrid"
3. 检查生成的 prompt.txt 是否包含 "本次日志分析模式为 hybrid"
4. 观察 agent 执行日志，确认是否按 hybrid 模式执行（先读摘要，再读完整目录）
