# AI 配置中心说明

## 入口

- 菜单：系统管理 -> AI配置中心
- 路由：`/system/aiconfig`

## 页面目标

把工单相关的 AI 配置集中到一个页面，减少在“参数设置”“AI Provider 管理”“AI 提示词管理”“AI 执行审计”“AI 仓库映射”之间来回切换。
页面顶部的说明区改成了独立说明块，避免说明内容被压成一小条。

## 可配置内容

### 1. 轻量 AI 配置

这部分影响工单保存与关闭时触发的轻量 AI 流程。

- `ticket.ai.translate.provider.code`
- `ticket.ai.translate.prompt.code`
- `ticket.ai.knowledge.provider.code`
- `ticket.ai.knowledge.prompt.code`

### 2. AI 分析 Worker 配置

这部分影响工单版本仓库分析任务的执行方式。

- `ticket.ai.worker.command`
- `ticket.ai.worker.model`
- `ticket.ai.worker.sandbox`
- `ticket.ai.worker.timeoutSec`
- `ticket.ai.workspace.root`
- `ticket.ai.agent.code`

## 执行时机

- 工单新增/编辑保存时执行轻量翻译
- 工单状态变更到 `CLOSED` 时执行知识提炼
- 工单 AI 分析任务创建时读取 Worker 配置和仓库映射

## 配置建议

- 翻译 Provider 和知识提炼 Provider 可以先配同一个，也可以拆分成两个独立 Provider。
- 翻译提示词默认建议保留 `ticket_translate_default`。
- 知识提炼提示词默认建议保留 `ticket_knowledge_extract_default`。
- `ticket.ai.worker.command` 默认是 `codex exec`，除非你明确切换到别的执行器。
- `ticket.ai.worker.sandbox` 默认是 `workspace-write`，一般不建议乱改。
- `ticket.ai.worker.timeoutSec` 建议至少 1800 秒，复杂仓库分析可更高。
- `ticket.ai.workspace.root` 建议保持为可写目录，且不要放在容易清理的临时目录。

## 快捷入口

页面右侧提供以下入口：

- AI Provider 管理
- AI 提示词管理
- AI 执行审计
- AI 仓库映射

## 与其他页面的关系

- `AI Provider 管理` 负责维护多个供应商、密钥、模型、等级和 Base URL。
- `AI 提示词管理` 负责维护翻译、知识提炼和分析追加模板。
- `AI 执行审计` 负责查看轻量 AI 调用的请求、响应和错误记录。
- `AI 仓库映射` 负责维护版本号到仓库、分支和 Worker 配置的映射。
