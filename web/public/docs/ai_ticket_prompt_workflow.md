# 工单 AI 提示词与轻量任务设计

## 目标

把工单系统里的 AI 能力拆成两类：

1. 轻量任务：翻译、版本提取、信息抽取、分类。
2. 重型任务：工单深度分析、RCA、知识沉淀，继续由 Codex 负责。

## 当前实现

### 1. AI Provider

系统管理里已支持配置多个 AI Provider：

- `provider_code`
- `provider_name`
- `provider_type`
- `agent_code`
- `model_name`
- `provider_level`
- `base_url`
- `api_key`

轻量任务优先走 Provider 的 OpenAI-compatible 接口。

### 2. AI 提示词模板

新增 `AI 提示词模板管理`，模板按分类维护：

- `translate`：工单翻译
- `version_extract`：版本提取
- `analysis`：工单分析追加提示词
- `common`：通用追加模板
- `knowledge`：知识沉淀模板

模板字段重点是：

- `template_code`
- `template_name`
- `template_category`
- `prompt_content`
- `provider_code`
- `model_name`
- `enabled`
- `sort`

### 3. 工单翻译

工单新增/编辑后，会调用轻量 AI 翻译：

- 翻译 Provider 由系统参数配置
- 翻译提示词模板由系统参数配置
- 翻译结果会追加到工单描述后
- 原文会保存在 `extra_data.origin_description`

### 4. 版本提取

版本号优先规则：

1. 前端手动填写版本号
2. 工单标题 + 描述内用正则提取版本号
3. 日志拉取后继续从日志里提取并回写

### 5. 工单分析

工单 AI 分析仍然使用 Codex。

新增了“追加提示词”能力：

- 在分析弹窗里可以多选模板
- 提交时会把选中的模板内容追加到当前分析提示词中
- 这样可以按场景注入不同的分析约束，而不改 Codex 主流程

## 系统参数

新增的轻量任务参数：

- `ticket.ai.translate.provider.code`
- `ticket.ai.translate.prompt.code`

这两个参数可以在系统参数页提前配置。

## 后续扩展建议

1. 把 `version_extract` 做成独立模板，后续如果正则命中率不足，可切换 LLM 兜底。
2. 给轻量任务加 `ai_task_execution` 记录，方便审计每次调用使用了哪个 Provider、模板和返回结果。
3. 工单关闭时增加知识抽取任务，沉淀为 `knowledge_case`。
