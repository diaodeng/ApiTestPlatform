# 工单轻量 AI 使用说明

## 概述

工单系统有两类 AI 能力：

| 类型 | 说明 | 运行方式 |
|------|------|----------|
| **轻量 AI** | 翻译、知识提炼、分类统计 | 调用 OpenAI-compatible 接口，快速返回 |
| **重型 AI** | 工单深度分析、RCA、知识沉淀 | 由 Codex Agent 执行，耗时较长 |

本文档说明轻量 AI 部分。重型 AI 分析请参考 AI 分析功能相关文档。

## 轻量 AI 能力一览

| 能力 | 触发时机 | 说明 |
|------|----------|------|
| 工单翻译 | 工单新增/编辑保存时 | 将工单描述翻译为中文，追加到描述后 |
| 知识提炼 | 工单状态变更为"已关闭"时 | 自动提炼知识库案例 |
| 分类统计 | 工单同步/新增/编辑保存时 | 自动对工单进行 AI 分类 |

所有轻量 AI 调用均为**尽力而为**：失败不会阻断工单保存或关单，原文会保留在 `extra_data` 中。

---

## 一、配置入口

轻量 AI 的配置集中在 **系统管理 → AI配置中心**（路由：`/system/aiconfig`）。

页面分为两个区域：

### 1.1 轻量 AI 配置区

设置翻译和知识提炼使用的 Provider 和提示词：

| 配置项 | 含义 | 系统参数键 |
|--------|------|-----------|
| 翻译 Provider | 翻译使用的 AI Provider 编码 | `ticket.ai.translate.provider.code` |
| 翻译提示词 | 翻译使用的提示词模板编码 | `ticket.ai.translate.prompt.code` |
| 知识提炼 Provider | 知识提炼使用的 AI Provider 编码 | `ticket.ai.knowledge.provider.code` |
| 知识提炼提示词 | 知识提炼使用的提示词模板编码 | `ticket.ai.knowledge.prompt.code` |
| 分类 Provider | 分类统计使用的 Provider 编码（兜底值） | `ticket.ai.category.classify.provider.code` |
| 分类提示词 | 分类统计使用的提示词编码（兜底值） | `ticket.ai.category.classify.prompt.code` |

左侧配置区修改后即时保存到系统参数；分类的详细场景开关在"工单同步配置"页配置。

### 1.2 AI 分析 Worker 配置区

设置重型 AI（Codex Worker）的执行参数：

| 配置项 | 含义 | 默认值 |
|--------|------|--------|
| Worker 命令 | Codex 执行命令 | `codex exec` |
| 模型 | Worker 使用的模型 | — |
| 沙箱模式 | 沙箱安全级别 | `workspace-write` |
| 超时时间（秒） | Worker 执行超时 | 1800 |
| 工作区根目录 | Worker 工作目录 | — |
| Agent 编码 | 使用的 Agent 编码 | — |

### 1.3 快捷入口

AI 配置中心右侧提供快捷跳转：
- **AI Provider 管理**：维护 Provider 接入信息
- **AI 提示词管理**：维护提示词模板
- **AI 执行审计**：查看轻量 AI 调用记录
- **AI 仓库映射**：维护版本号到仓库的映射

---

## 二、AI Provider 管理

**入口**：系统管理 → AI Provider管理（路由：`/system/aiprovider`）

Provider 是 AI 服务的接入配置，每条记录对应一个可用的 AI 接口。

### 2.1 配置项

| 字段 | 说明 | 示例 |
|------|------|------|
| Provider 编码 | 唯一标识，其他配置通过编码引用 | `translate_main` |
| Provider 名称 | 显示名称 | `工单翻译主账号` |
| Provider 类型 | 接口类型 | `openai`、`azure_openai`、`ollama`、`custom` |
| Agent 编码 | 绑定的 Agent（可选，用于重型分析） | — |
| 模型名称 | 默认模型 | `gpt-4.1-mini` |
| Provider 等级 | 优先级 | `10` |
| Base URL | API 基础地址 | `https://ai-gateway.example.com/v1` |
| API Key | 密钥（加密存储） | — |
| 扩展配置 | 额外环境变量（Worker 时注入） | — |
| 启用 | 是否启用 | true/false |

### 2.2 生效链路

- **工单 AI 分析弹窗**：可直接选择 Provider
- **协同消息**：可指定 Provider，创建 AI 任务时沿用
- **日志拉取配置**：可选择 Provider，自动 AI 时使用
- **轻量 AI**：按系统参数中的 Provider 编码查找对应配置

Provider 未启用时，提交任务会直接拒绝。Provider 和 Agent 都为空时，不允许启用自动 AI。

### 2.3 URL 格式兼容

轻量翻译链路兼容以下两种 URL 格式：
- 基础地址：`https://ai-gateway.example.com/v1`（自动补 `/chat/completions`）
- 完整路径：`https://ai-gateway.example.com/v1/responses` 或 `/chat/completions`

---

## 三、AI 提示词管理

**入口**：系统管理 → AI提示词管理

提示词模板按 **分类（category）** 组织，不同分类对应不同的使用场景。

### 3.1 模板分类

| 分类 | 用途 | 默认模板编码 |
|------|------|-------------|
| `translate` | 工单翻译 | `ticket_translate_default` |
| `knowledge` | 知识沉淀/提炼 | `ticket_knowledge_extract_default` |
| `analysis` | 工单分析追加提示词 | — |
| `common` | 通用追加模板 | — |

### 3.2 模板字段

| 字段 | 说明 |
|------|------|
| 模板编码 | 唯一标识，配置中通过编码引用 |
| 模板名称 | 显示名称 |
| 模板分类 | `translate` / `knowledge` / `analysis` / `common` |
| 提示词内容 | 提示词正文 |
| 关联 Provider | 可选的默认 Provider（优先级低于系统参数） |
| 关联模型 | 可选的默认模型 |
| 排序 | 列表排序权重 |
| 启用 | 是否启用 |

### 3.3 分析追加提示词

工单 AI 分析弹窗中可多选 `analysis` 和 `common` 分类的模板。提交分析任务时，选中的模板内容会追加到分析提示词中，实现按场景注入不同约束而不修改主流程。

---

## 四、工单翻译

### 4.1 触发时机

工单新增或编辑保存时自动调用。

### 4.2 配置方法

1. 在 **AI Provider 管理** 中添加一个翻译专用 Provider（类型 `openai`，建议用小模型如 `gpt-4.1-mini`）
2. 在 **AI 提示词管理** 中添加翻译提示词模板（分类 `translate`）
3. 在 **AI 配置中心** 设置翻译 Provider 和提示词编码

### 4.3 翻译规则

- 保留版本号、错误码、IP、路径、SQL 等技术信息
- 翻译结果直接可读，不输出额外解释
- 不会擅自删除技术术语
- 原文保存在 `extra_data.origin_description`
- 若翻译失败，工单保存不受影响，保留原文

### 4.4 手动自动翻译

工单新增/编辑页提供"手动自动翻译"开关，最终值保存到 `extraData.manualAutomation.autoTranslate`。关闭后手动新增/编辑不再调用翻译。

---

## 五、知识提炼

### 5.1 触发时机

工单状态流转到"已关闭"时自动调用。

### 5.2 执行流程

1. 读取知识提炼 Provider 和提示词配置
2. 调用 AI 接口进行结构化输出
3. 成功时写入知识库案例（`knowledge_article`）
4. 若 AI 提炼失败，回退到规则拼装的知识文章

### 5.3 配置方法

与翻译配置方法相同，在 AI 配置中心的"知识提炼"区域设置对应的 Provider 和提示词。

---

## 六、分类统计

工单分类统计的 Provider 和提示词在 **AI Provider 管理** 和 **AI 提示词管理** 中维护。

**工单同步配置** 页面提供场景开关：`ticket.sync.automation.aiClassification`
- 控制外部同步、远端拉取、手动创建场景是否执行分类
- 选择 Provider 编码和提示词编码
- 提示词正文统一在 AI 提示词管理维护，不在此处填写

---

## 七、AI 执行审计

**入口**：系统管理 → AI执行审计（路由：`/system/aitaskexecution`）

### 7.1 审计内容

所有轻量 AI 调用会自动记录到审计表 `sys_ai_task_execution`，包括：

| 字段 | 内容 |
|------|------|
| 任务类型 | `ticket_translate`、`ticket_knowledge_extract` 等 |
| 来源信息 | 来源类型、来源 ID |
| 调用配置 | Provider、提示词、模型、Base URL |
| 请求内容 | 发送给 AI 的完整请求 |
| 响应内容 | AI 返回的响应 |
| Token 用量 | 消耗的 Token 数量 |
| 状态 | `pending` / `running` / `success` / `failed` / `skipped` |
| 错误信息 | 失败原因 |

### 7.2 页面功能

- 按任务类型、来源类型、Provider、状态和关键字分页查询
- 查看单条审计详情（请求/响应/Token/错误）
- 只读页面，不提供编辑和删除

---

## 八、配置示例

### 8.1 翻译配置示例

**Step 1：创建翻译 Provider**
- Provider 编码：`translate_main`
- Provider 名称：`工单翻译主账号`
- Provider 类型：`openai`
- 模型名称：`gpt-4.1-mini`
- Provider 等级：`10`
- Base URL：`https://ai-gateway.example.com/v1`
- API Key：你的密钥
- 启用：是

**Step 2：创建翻译提示词**
- 模板编码：`ticket_translate_default`
- 模板名称：`工单翻译默认提示词`
- 模板分类：`translate`
- 提示词内容：`你是专业的工单翻译助手...`

**Step 3：配置 AI 配置中心**
- 翻译 Provider：`translate_main`
- 翻译提示词：`ticket_translate_default`

### 8.2 分析追加提示词示例

创建 `analysis` 分类模板：
- 模板编码：`analysis_keep_debug`
- 模板分类：`analysis`
- 提示词内容：`优先定位根因，不要只给泛化建议，输出必须包含证据和下一步动作。`

工单 AI 分析时在弹窗中多选该模板，提交后内容自动追加到分析提示词中。

---

## 九、常见问题

### Q1: 翻译没生效？

检查：① AI 配置中心是否配置了翻译 Provider 和提示词编码 ② Provider 是否已启用 ③ AI 执行审计中是否有对应记录及错误信息

### Q2: 翻译结果不对？

可调整提示词模板的内容。在 AI 提示词管理中修改模板后立即生效。

### Q3: 知识提炼失败会影响关单吗？

不会。轻量 AI 是尽力而为，失败会回退到规则拼装的知识文章，不会阻断工单关闭。

### Q4: 如何切换翻译/知识提炼使用的模型？

在 AI Provider 管理中修改对应 Provider 的模型名称，或创建新的 Provider 后在 AI 配置中心切换引用。

---

## 十、相关文档

- [AI Provider 管理说明](ai_provider_management.md)
- [AI 配置中心说明](ai_config_center.md)
- [AI 执行审计说明](ai_task_execution_page.md)
- [工单同步自动化说明](ticket-sync-automation.md)
