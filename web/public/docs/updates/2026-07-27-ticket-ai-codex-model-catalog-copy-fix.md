# 工单 AI 分析 Codex 模型目录复制修复

## 结论

Agent 为每个工单 AI 任务创建独立 `CODEX_HOME` 时，现会同步复制 `config.toml` 中
`model_catalog_json` 引用的相对模型目录文件，修复 Codex Worker 启动后立即返回
`系统找不到指定的文件。 (os error 2)` 的问题。

## 问题现象与根因

故障任务能够成功执行 `codex.cmd`，但约 0.5 秒内以返回码 1 退出，且没有标准输出。
现场检查发现：

- `codex.cmd`、`-C` 指定的 Git worktree、任务工作区和 `result.schema.json` 均存在；
- 任务级 `.codex_home/config.toml` 包含 `model_catalog_json = "cc-switch-model-catalog.json"`；
- 用户级 Codex Home 中存在该 JSON 文件，任务级 `.codex_home` 中不存在；
- Codex 会相对当前 `CODEX_HOME` 加载模型目录，因此在发起模型请求前即因缺文件退出。

## 实现设计

- 新增 `TicketAiCodexConfigService`，单独负责复制任务级 Codex 配置文件。
- 复制基础配置后使用 Python 标准库 `tomllib` 读取 `model_catalog_json`。
- 相对路径保持原目录结构复制到任务级 Codex Home；目标文件已存在时不覆盖，保留任务重试现场。
- 绝对路径存在时直接复用；引用文件不存在或相对路径越出 Codex Home 时，在启动 Worker 前返回明确错误。
- 日志记录实际复制的文件，以及未配置、文件不存在或已存在时跳过的原因。

## 验证

- `uv run python -m unittest discover -s tests -p 'test_ticket_ai_codex_config_service.py' -v`
- `uv run python -m compileall -q services/ticket_ai_codex_config_service.py services/ticket_ai_analysis_service.py tests/test_ticket_ai_codex_config_service.py`

覆盖场景：相对模型目录成功复制、引用文件缺失时明确失败、未配置模型目录时正常跳过，
以及任务目标文件已存在时保留重试现场。

另使用故障任务的 `.codex_home` 副本做了真实 Codex 启动验证：补齐模型目录后，Codex 已正常
加载 worktree、模型和 Provider，并到达 `https://codeai.ysaikeji.cn/v1/responses`；不再出现
`os error 2`。该旧任务配置副本随后收到 `401 Unauthorized: Invalid token`，说明文件缺失问题已解除；
正式重试会重新写入服务端当前下发的 Provider 配置，但重试前仍建议确认 `codeai` 的现用 API Key 有效。

## 回滚

如需回滚，移除 `TicketAiAnalysisService._prepare_codex_home` 对
`TicketAiCodexConfigService.copy_task_home_files` 的调用，并恢复原基础文件复制逻辑即可。
回滚后，任何包含相对 `model_catalog_json` 的 Codex 配置都会再次面临任务级文件缺失风险。
