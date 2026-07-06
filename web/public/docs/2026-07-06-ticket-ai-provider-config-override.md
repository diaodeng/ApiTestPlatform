# 2026-07-06 工单 AI 分析 Provider 配置下发修复

## 问题
工单 AI 分析时，后端下发了 `providerEnv`（含 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` 等），
但 Agent 端 Codex CLI 仍然使用本地全局配置，导致 401 鉴权失败或请求打到错误的 base_url。

## 根因
Agent 端 `_prepare_codex_home` 方法将全局 `~/.codex/` 下的配置文件原样复制到任务级 `.codex_home` 目录：
- `config.toml` 中的 `model_providers.custom.base_url` 优先级高于 `OPENAI_BASE_URL` 环境变量
- `auth.json` 中的 `OPENAI_API_KEY` 优先级高于环境变量

因此即使后端正确下发了 `providerEnv`，Codex CLI 仍读取本地全局配置。

## 修复内容

### 1. Agent 端 `client_new/services/ticket_ai_analysis_service.py`
- `_prepare_codex_home` 新增 `provider_env_overrides` 参数
- 有 Provider 覆盖时跳过复制 `auth.json`，避免本地全局 API Key 覆盖下发配置
- 新增 `_patch_codex_config_for_provider` 方法：
  - 修改副本 `config.toml` 中的 `base_url` 为 Provider 下发的值
  - 修改副本 `.env` 中的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`
- 调用处传入 `provider_env_overrides`

### 2. Server 端 `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`
- 同样的 `_prepare_codex_home` 和 `_patch_codex_config_for_provider` 修改
- `_build_worker_command` 新增 `provider_env_overrides` 参数并透传

## 配置优先级（修复后）
1. Provider 下发的 `OPENAI_BASE_URL` → 写入副本 `config.toml` 的 `base_url` 和 `.env`
2. Provider 下发的 `OPENAI_API_KEY` → 写入副本 `.env`，不复制 `auth.json`
3. Provider 下发的 `OPENAI_MODEL` → 通过 `-m` 命令行参数传递
4. 本地 Codex 全局配置 → 仅在没有 Provider 覆盖时生效

## 验证
- 两个文件编译通过
- 需要实际运行 Agent 并发起 AI 分析任务验证 Provider 配置是否正确生效
