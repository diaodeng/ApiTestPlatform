# AI Provider 平台、协议、能力与模型目录改造

## 改造目的

AI Provider 不再使用单一“类型”混合表达供应商、调用协议和业务用途。新模型将平台、协议、用途和执行器拆分，避免把能保存的 Provider 错误展示到不能执行的工单场景。

## 新 Provider 配置

- 平台：OpenAI、OpenAI 兼容网关、Azure OpenAI、Anthropic、Ollama 或自定义。
- API 协议：OpenAI Chat Completions、OpenAI Responses、Azure OpenAI Chat、Anthropic Messages、Ollama Chat 或自定义。
- 支持用途：工单轻量 AI、工单 AI 分析、工单向量化、模型目录发现。
- 兼容执行器：服务端直连、Codex Worker、Claude Code Worker。
- 默认模型：支持从模型目录选择，也可手工输入。
- 协议配置：Azure deployment/API Version 等协议专属 JSON 配置。
- Worker 环境：仅用于分析 Worker 的环境变量覆盖，不再与协议配置混用。
- Base URL：应填写服务根地址（OpenAI 可包含 `/v1`）；即使误填了 Chat、Responses、Anthropic Messages、Ollama 或 Azure 的具体接口路径，运行时会规范化为服务根地址后再拼装请求。

## 模型目录与密钥

1. 新增或编辑 Provider 时可点击“更新模型”。新增场景使用当前表单地址和密钥进行一次性探测，不保存密钥；已保存 Provider 且未修改密钥时使用服务端密文探测并刷新目录缓存。
2. 当前自动模型目录支持 OpenAI Chat/Responses、Anthropic Messages 和 Ollama Chat。Azure 和自定义协议保留手工填写模型，不能承诺从推理地址获取可部署模型。
3. Provider 密钥默认只返回掩码。点击“查看密钥”必须拥有 `system:aiprovider:view-secret` 权限并输入当前登录用户密码，密钥不会写入日志或详情接口。

## 场景过滤与服务端校验

- 工单轻量 AI 的 Provider 下拉仅请求 `ticket_light_text + direct_http`。
- 工单 AI 分析、协同追问和日志拉取后的自动分析仅请求 `ticket_analysis_worker + codex`。
- AI 提示词的默认 Provider 会按提示词分类加载对应场景的候选。
- 前端筛选只是体验层；服务端在轻量 AI 实际调用及分析 Worker 提交/执行前再次校验用途和执行器，不兼容时直接拒绝。

## 数据库操作

执行 [20260728_ai_provider_capability_model.sql](../../../server/sql/20260728_ai_provider_capability_model.sql) 前必须备份 `sys_ai_provider`。该脚本包含 DDL，MySQL 会隐式提交，应在维护窗口逐句执行并验证，不要依赖事务回滚。脚本会删除旧 `provider_type`，不会维护旧字段兼容；所有旧 Provider 会被初始化为无用途、无执行器，管理员必须重新确认配置后才会出现在下拉候选中。

## 影响范围

- 系统管理的 AI Provider 管理和 AI 提示词管理。
- 工单同步自动化的翻译、提取、分类、标题总结、知识提炼和汇总解读配置。
- 工单详情、协同、日志拉取及日志拉取管理页的 AI 分析 Provider 选择。
- 工单轻量 AI 直连调用和工单 AI 分析 Worker 下发。
