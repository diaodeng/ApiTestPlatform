---
title: 轻量 AI 与向量化 Token 用量审计接入
---

# 轻量 AI 与向量化 Token 用量审计接入

## 变更内容

- 协议层新增 `generate_text_with_usage`：OpenAI Chat/Responses/Azure、Anthropic、Ollama 各协议在生成文本的同时透出上游 Token 用量；原 `generate_text` 保持 `str` 返回签名，旧调用方无需改动。
- 轻量 AI 全部场景（翻译、知识提炼、分类统计、同步统一提取、标题总结）的成功审计记录现在写入真实 `token_usage`，此前全部为 null。
- 专题工单 AI 分类（`classify_category_with_ai`）新增用量透出：逐条调用的用量在批次内累加（`batch_token_usage` 容器），补齐此前完全无统计的飞书群分类链路。
- 专题分类批次审计落库：批次真实发生 AI 调用时写入汇总审计记录（`ticket_topic_classify`），含累加用量、调用/成功/失败次数与统计结果摘要；全部失败落 `failed` 记录；零调用（关键词模式或无命中消息）不落库。
- 外部向量化（OpenAI 兼容 `/v1/embeddings`）调用进入审计：新增任务类型 `ticket_embedding`，记录 Provider、模型、endpoint、文本长度和上游 `prompt_tokens/total_tokens`；本地哈希向量化不产生外部请求，不写审计。
- 向量化审计写入失败只告警，不阻断向量化主流程。

## 用量口径

- 文本生成：单次调用一条审计记录，`token_usage` 为该次请求的用量。
- 专题分类批次：多条调用累加进 `batch_token_usage`，键名保留上游原始字段。
- Embedding：单条文本一次请求一条审计记录，用量为该次请求的 `prompt_tokens/total_tokens`。
- 缓存命中（同步提取同源缓存、向量内容哈希复用）不发请求，无用量记录。

## 注意事项

- 修复前历史审计记录的 `token_usage` 均为 JSON 文本 `'null'`，统计时需排除。
- 真实验证：使用 `.env.prod` Provider 配置（`openai_responses` 与 `openai_chat_completions` 双协议）实际调用 AI 接口，用量分别解析为 `{'input_tokens': 42, 'output_tokens': 20, 'total_tokens': 62}` 和 `{'prompt_tokens': 95, 'completion_tokens': 9, 'total_tokens': 104}`；embeddings 用量提取经 mock 响应验证。
- 验证脚本：`server/scripts/verify_live_usage_call.py`（真实调用，不写库）、`server/scripts/verify_light_ai_token_usage.py`（只读查询审计表覆盖率）。
