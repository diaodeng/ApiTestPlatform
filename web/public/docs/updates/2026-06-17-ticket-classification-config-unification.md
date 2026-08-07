# 工单分类配置统一方案

## 背景

工单分类相关配置原先分散在工单同步配置和系统管理 AI 配置中心：

- `ticket.sync.automation.statClassification`：维护工单类型、根因、解决方式、关闭结果枚举。
- `ticket.sync.automation.aiClassification`：控制分类统计在外部同步、远端拉取、手动创建场景是否执行，并保存 Provider、提示词编码和历史内联提示词。
- `ticket.ai.category.classify.*`：系统 AI 配置中心的旧分类 Provider、提示词和总开关。
- AI Provider / AI 提示词模板：真实维护模型连接和提示词正文。

这些配置职责混在同一页面后，容易误以为修改同步配置中的提示词正文才是唯一生效路径，也容易因保存同步配置覆盖历史提示词导致分类行为变化。

## 本次统一

1. AI Provider 和提示词正文统一由系统管理中的 AI Provider 管理、AI 提示词管理维护。
2. 工单同步配置页的 AI 分类统计只保留场景开关、Provider 编码和提示词编码选择，不再提供新的提示词正文编辑入口。
3. `ticket_stat_classify_default` 默认提示词模板由启动初始化补齐为内置结构化分类统计提示词，避免默认模板为空导致 AI 分类统计不可用。
4. 清理旧默认模板 `ticket_category_classify_default`：启动初始化时会将历史模板逻辑删除，分类统计默认值统一使用 `ticket_stat_classify_default`。
5. 旧版 `ticket.sync.automation.aiClassification.promptContent` 不删除，保存同步配置时如果新提交为空会保留旧值；后端只在默认模板缺失或为空时把它作为兜底，避免现有业务突然变化。
6. 批量重归类入口的 AI 提示词编码改为从提示词模板下拉选择，留空时使用当前分类统计配置。

## 当前自动处理数据

AI 分类统计会使用以下上下文：

- 工单标题、工单描述。
- 最近工单评论，按时间顺序拼入上下文。
- 当前工单已有字段：工单号、历史分类、工单类型、模块、状态、是否真实问题、根因分类、解决方式、关闭结果、严重程度、根因与解决方案。
- 同步配置中的统计枚举：工单类型、根因分类、解决方式、关闭结果。

自动触发场景：

- 外部同步入库后。
- 远端拉取入库后。
- 手动创建工单后。
- 同步配置页批量重归类。

回填字段：

- 主表字段：`category_name`、`issue_type_id`、`issue_type_name`、`module_name`、`severity`、`root_cause_type`、`solution_type`、`resolution_code`、`resolution_name`、`root_cause`、`solution`、`is_problem`。
- 执行摘要：`extra_data.ai_classification`，包含来源 hash、评论数量、Provider、Prompt、执行时间、置信度、原因、是否需要研发/监控/知识库、模型原始 JSON。

## 页面分组

同步配置页按职责展示为：

- 基础配置：同步后自动执行、同步后自动翻译、默认拉取数量、远端来源系统、飞书统一凭证、统计枚举。
- 拉取配置：远端同步链接、拉日志默认值。
- 推送配置：外部推送多维表格邮箱补全、群消息推送、按人催办、汇总通知。
- 手动配置：AI 分类统计场景开关和批量重归类工具。

## 兼容策略

- 现有 `ticket.sync.automation.aiClassification.providerCode/promptCode` 继续生效。
- 现有 `ticket.sync.automation.aiClassification.promptContent` 继续保留，但只作为历史兜底，不再作为新配置入口。
- 如果分类统计配置没有选择 Provider，后端仍会回退到 `ticket.ai.category.classify.provider.code`。
- 如果分类统计配置没有选择 Prompt，后端仍会回退到 `ticket.ai.category.classify.prompt.code` 或默认 `ticket_stat_classify_default`；旧值 `ticket_category_classify_default` 会自动映射为 `ticket_stat_classify_default`。
- `statClassification` 枚举仍保存在 `ticket.sync.automation`，因为它是工单业务枚举，不属于 AI Provider/Prompt 底座配置。

## 影响范围

- 不修改外部同步、远端拉取、手工创建、批量重归类的接口路径。
- 不删除历史配置字段。
- 不执行数据库结构迁移。
- 只调整配置来源优先级和页面编辑入口，降低误操作风险。
