# 工单知识提炼与轻量 AI 审计说明

## 目标

- 工单关闭后自动提炼知识库案例。
- 轻量 AI 调用统一写入审计表，方便排查和后续扩展。

## 新增配置

### 工单翻译

- `ticket.ai.translate.provider.code`
- `ticket.ai.translate.prompt.code`

用途：

- 工单新增/编辑时，使用配置的 Provider + 提示词模板做轻量翻译。
- 未配置时会直接回退原文，不影响工单保存。

### 工单知识提炼

- `ticket.ai.knowledge.provider.code`
- `ticket.ai.knowledge.prompt.code`

用途：

- 工单关闭后自动提炼知识库案例。
- 默认会先尝试 AI 结构化输出，再回退到规则拼装的知识文章。

## 默认提示词模板

- `ticket_translate_default`
- `ticket_knowledge_extract_default`

说明：

- 系统启动时会自动补默认模板。
- 你可以在“AI提示词管理”里继续调整内容。

## 审计表

表名：

- `sys_ai_task_execution`

主要字段：

- `task_type`：任务类型，比如 `ticket_translate`、`ticket_knowledge_extract`
- `task_name`：任务名称
- `source_type` / `source_id` / `source_ref`：来源信息
- `provider_code` / `prompt_code` / `model_name` / `base_url`：调用配置
- `request_payload`：请求内容
- `response_payload` / `response_text`：响应内容
- `status`：`pending`、`running`、`success`、`failed`、`skipped`
- `error_message`：错误信息

## 运行方式

### 工单翻译

1. 配置翻译 Provider。
2. 配置翻译 Prompt。
3. 新增或编辑工单时自动调用。

### 工单知识提炼

1. 配置知识提炼 Provider。
2. 配置知识提炼 Prompt。
3. 工单状态流转到关闭时自动调用。
4. 若 AI 提炼失败，系统会回退到现有的规则拼装知识文章。

## 说明

- 轻量 AI 调用是尽力而为，不会阻断工单保存或关单。
- 审计表记录的是实际调用痕迹，便于追踪 Provider、模板和错误原因。
