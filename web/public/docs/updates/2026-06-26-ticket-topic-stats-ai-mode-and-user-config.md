# 2026-06-26 专题工单统计新增 AI 模式与用户配置兜底

## 变更目标

`module_task.scheduler_maintenance.ticket_topic_stats_report` 新增分类模式开关，保留原有关键词模式，同时支持 AI 自动分类模式。

## 新增能力

1. 任务参数新增 `categoryMode`。
   - `keywords`：继续使用原有关键词匹配逻辑。
   - `ai`：启用 AI 自动分类逻辑。
2. 任务参数新增 AI 配置项。
   - `aiProviderCode`
   - `aiPromptCode`
   - `aiPromptContent`
3. AI 配置支持两层兜底。
   - 任务参数优先。
   - 若任务参数未配置，则读取当前任务归属用户的 `sys_user_config`。
   - 若用户未单独配置，则继续回退到系统参数默认值。

## AI 模式行为

- 使用现有 AI Provider 的 OpenAI 兼容接口。
- 默认系统提示词会要求模型输出 JSON。
- 用户可手动配置 `aiPromptContent` 覆盖默认提示词，也可只配置提示词模板编码。
- 若 AI 解析失败，任务会保留原有关键词模式作为可用兜底思路，避免任务整体中断。

## 用户配置约定

- 配置类型：`ticket`
- 配置键名：`ticket_topic_stats_report`
- 配置内容建议结构：

```json
{
  "categoryMode": "ai",
  "providerCode": "your_provider_code",
  "promptCode": "ticket_stat_classify_default",
  "promptContent": "自定义提示词正文，可为空"
}
```

## 调用建议

- 仅想切换模式时，传 `categoryMode=ai` 即可。
- 想指定全局 AI Provider 时，传 `aiProviderCode`。
- 想使用自定义提示词时，传 `aiPromptContent`。
- 如果不传这些参数，任务会优先读取任务归属用户配置，再回退到系统默认配置。

## 说明

- 关键词模式已保留，默认仍是 `keywords`。
- 这次改动是任务级能力，不会影响工单同步、标题翻译或知识提炼链路。
