# 工单轻量 AI 配置收敛到工单同步配置

## 结论

工单翻译、标题总结、工单分类、参数提取和知识提炼的开关、Provider 与提示词编码，统一由系统参数 `ticket.sync.automation` 管理，配置入口统一为“工单管理 -> 工单同步配置”。“AI 配置中心”只保留 AI 分析 Worker 配置。

旧的 `ticket.ai.translate.*`、`ticket.ai.title.summary.*`、`ticket.ai.category.classify.*`、`ticket.ai.log_extract.*`、`ticket.ai.knowledge.*` 不再读取、不再写入，也不会在启动时创建。历史数据库行可以继续存在，但不会生效；本次不迁移旧值，也不提供兼容回退。

## 配置结构

| 能力 | `ticket.sync.automation` 配置段 | 必要配置 |
|---|---|---|
| 工单翻译 | `translateConfig` | `enabled`、对应场景开关、`providerCode`、`promptCode` |
| 标题总结 | `titleSummaryConfig` | `enabled`、`providerCode`、`promptCode` |
| 工单分类 | `aiClassification` | `enabled`、对应场景开关、`providerCode`、`promptCode` |
| 参数提取 | `aiSyncExtract` | 对应场景开关、`providerCode`、`promptCode`、`extractFields` |
| 知识提炼 | `knowledgeConfig` | `enabled`、`providerCode`、`promptCode` |

Provider 必须是已启用的 AI Provider，提示词编码必须对应已启用的提示词模板。配置段开关开启但 Provider 或提示词为空时，任务会记录跳过日志，不调用模型。

## 定时任务优先级

飞书多维表格主动拉取定时任务遵循以下优先级：

1. 任务参数显式提供 `bitablePull.automation` 或 `bitable_pull.automation` 时，使用任务级自动化配置。
2. 任务参数没有提供 `automation` 时，不构造默认任务配置，后处理按 `ticket.sync.automation` 中 `bitable_pull` 场景开关执行。
3. 保存全局同步配置时会移除 `bitablePull.automation`，避免把任务级参数混入全局配置。

## 群推送条件

群推送条件新增 `status_name` 字段。该字段通过工单的 `status` 编码查询工作流状态配置，值为状态显示名；`status` 继续表示状态编码。

按中文状态判断时必须使用显示名字段，例如：

```text
status_name in ['2. 1.5线处理', '3. 待产研处理'] and has(module_id)
```

如果状态编码在工作流配置中不存在，`status_name` 为空字符串，依赖显示名的条件不会命中。

## 部署后操作

1. 在“工单同步配置”中重新维护五类轻量 AI 配置；旧 AI 配置中心中的值不会自动带入。
2. 确认所选 Provider 已启用，所选提示词模板存在且已启用。
3. 检查多维表格主动拉取定时任务参数：需要任务级覆盖时提供完整 `automation`，否则删除该参数并使用同步配置。
4. 将群推送条件中使用中文状态文本的 `status` 改为 `status_name`。
5. 保存配置后分别触发测试工单，结合“执行/跳过原因”日志核对翻译、标题、分类、提取、知识提炼和群推送链路。

## 影响范围

- 旧 AI 配置中心轻量 AI 表单和接口字段已删除，调用方不能再通过聚合 AI 配置接口维护这些值。
- 分类内联 `promptContent` 已删除，分类提示词正文只从提示词模板表读取。
- `automationConfig.enabled` 已删除，各场景开关直接生效。
- 本次没有删除或修改生产数据库中的旧配置数据，也不需要数据库结构迁移。

