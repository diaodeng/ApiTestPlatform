# Agent Codex CLI 执行修复

## 背景

工单 AI 分析由服务端下发任务到 `client_new` Agent，再由 Agent 调用 `codex exec` 执行分析。近期 Windows 机器安装 Codex 桌面应用后，系统 PATH 中的 `codex` 解析到了：

```text
C:\Users\xj\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe
```

该路径位于 Codex 应用安装目录，但实际执行 `codex --version` 可能返回 `codex-cli`，说明它仍是 CLI 入口。不能只按路径判断是否可用，必须通过 `--version` 校验 CLI 身份。

## 本次调整

- Agent 解析 Codex Worker 时通过 `codex --version` 校验 CLI 身份；只要返回 `codex-cli`，即使路径位于 OpenAI Codex 安装目录也允许使用。
- 新增 Agent 本地配置 `ticket_ai_codex_cli_path`，可显式指定 Codex CLI 路径。
- CLI 解析优先级：
  1. `ticket_ai_codex_cli_path`
  2. `C:\nvm4w\nodejs\codex.cmd/exe`
  3. `%USERPROFILE%\AppData\Roaming\npm\codex.cmd/exe`
  4. PATH 中可通过 `--version` 校验的 `codex`
- Windows 下调用 Codex 子进程时隐藏控制台窗口，避免 Agent 机器弹出 cmd。
- Worker 失败时不再把完整 stdout/stderr 回传服务端，只返回错误摘要和工作区日志文件路径。
- Codex 返回 `Concurrency limit exceeded` 时，错误提示归一为账号并发限制，避免被业务日志内容污染。

## 使用说明

如果 Agent 机器的 `codex --version` 能返回 `codex-cli`，Agent 会直接使用该入口。若无法通过校验，AI 分析会明确提示找不到 Codex CLI，需要安装 CLI，或在 Agent 配置中填写：

```json
{
  "ticket_ai_codex_cli_path": "C:\\Users\\xj\\AppData\\Roaming\\npm\\codex.cmd"
}
```

工作区和仓库路径优先级保持不变：Agent 本地 `ticket_ai_workspace_root/ticket_ai_local_repo_path` 优先，其次使用服务端仓库映射下发的路径。

Provider 优先级保持不变：服务端下发 `providerEnv` 时覆盖本次 Worker 环境；未下发时使用 Agent 本地 Codex 配置。
