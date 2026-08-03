# 工单 AI 分类统计说明

## 目标

`ticket` 主表承担统计字段落点，AI 负责单条分析，不再单独建统计表。

## 回填字段

- `is_problem`
- `issue_type_id`
- `issue_type_name`
- `module_name`
- `severity`
- `root_cause_type`
- `solution_type`
- `resolution_code`
- `resolution_name`
- `root_cause`
- `solution`
- `extra_data.ai_classification`

## 配置项

系统参数 `ticket.sync.automation.aiClassification`：

- `enabled`
- `runOnExternalSync`
- `runOnRemotePull`
- `runOnManualCreate`
- `providerCode`
- `promptCode`
- `promptContent`

## 默认提示词

- 默认提示词编码：`ticket_stat_classify_default`
- 若用户未配置 `promptContent`，后端归一化配置时会回填内置结构化 JSON 提示词，配置页会直接展示默认内容，便于在默认规则基础上修改。
- AI 执行时优先使用 `promptContent` 作为 system prompt；具体工单标题、描述、评论、当前字段和候选枚举仍由 user prompt 单独承载，避免默认链路重复传递同一份业务上下文。

## 防重规则

- 以 `title + description + 最近评论上下文` 计算 hash
- 同文本且已有成功结果时跳过
- 手动强制重归类会覆盖跳过逻辑

## 说明

- 外部同步、远端拉取、手动创建可以分别控制是否触发 AI 分类
- 统计枚举由 `ticket.sync.automation.statClassification` 可视化维护
- AI 分类会结合工单标题、描述和最近评论判断；system prompt 只放角色、规则和输出契约，user prompt 放具体工单上下文，避免默认链路重复传同一份业务内容
