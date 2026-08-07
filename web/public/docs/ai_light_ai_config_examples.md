# 轻量 AI 配置示例

## 1. 轻量翻译链路怎么配

工单创建/编辑后走的是“轻量 AI 翻译”，它不走 Codex，只调用普通 AI Provider 接口。

### 推荐配置方式

在 `AI Provider` 里新增一个专门给翻译用的 Provider，例如：

- `provider_code`: `translate_main`
- `provider_name`: `工单翻译主账号`
- `provider_type`: `openai`
- `model_name`: `gpt-4.1-mini`
- `provider_level`: `10`
- `base_url`: `https://ai-gateway.dmall.com/9/openai/v1/responses`
- `api_key`: 你的网关密钥
- `enabled`: `true`

然后在系统参数里配置：

- `ticket.ai.translate.provider.code = translate_main`
- `ticket.ai.translate.prompt.code = ticket_translate_default`

这样工单创建/编辑后会自动翻译，并把翻译结果追加到工单描述后面。

### `responses` URL 可以吗

可以。

当前轻量翻译链路已经兼容：

- `/responses`
- `/chat/completions`

如果你的网关就是 `https://ai-gateway.dmall.com/9/openai/v1/responses`，可以直接填完整路径。

如果你更喜欢填基础地址，也可以填：

- `https://ai-gateway.dmall.com/9/openai/v1`

系统会默认按 `chat/completions` 补路径，但如果你直接填了 `/responses`，系统也会原样使用。

## 2. 翻译提示词模板怎么配

在 `AI 提示词管理` 中新增分类为 `translate` 的模板，例如：

- `template_code`: `ticket_translate_default`
- `template_name`: `工单翻译默认提示词`
- `template_category`: `translate`
- `prompt_content`: `你是专业的工单翻译助手...`

建议规则：

- 保留版本号、错误码、IP、路径、SQL
- 结果尽量直接可读，不要输出额外解释
- 不要擅自删除技术术语

## 3. 分析提示词怎么配

在 `AI 提示词管理` 中新增分类为 `analysis` 或 `common` 的模板。

工单 AI 分析弹窗里可以多选这些模板，提交后会追加到当前分析提示词中。

示例：

- `template_code`: `analysis_keep_debug`
- `template_category`: `analysis`
- `prompt_content`: `优先定位根因，不要只给泛化建议，输出必须包含证据和下一步动作。`

## 4. 版本提取怎么配

版本号提取当前优先使用正则，不依赖 AI：

- 工单手动填了版本号，直接用
- 没填时，从标题和描述中用正则提取
- 日志拉取后如果还没提取到，会继续从日志里补回写

如果你后面想把版本提取改成 LLM 兜底，可以再新增一个 `version_extract` 分类模板和一个独立任务入口。
