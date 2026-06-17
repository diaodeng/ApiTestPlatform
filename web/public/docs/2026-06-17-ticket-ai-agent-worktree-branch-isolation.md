# 工单 AI Agent 分支隔离说明

## 背景

工单 AI 分析由 `client_new` Agent 调用 `codex exec` 读取本地代码。不同工单可能映射到不同分支，如果多个分析任务共享同一个本地仓库目录，运行期间的分支状态会互相影响，导致 Codex 读取到错误分支代码。

## 调整内容

1. Agent 执行前优先使用仓库映射下发的 `localRepoPath`，并校验该目录当前 Git 分支必须等于映射的 `branchName`。
2. 如果映射未配置 `localRepoPath`，Agent 会按 `repoUrl + branchName` 在 AI 工作区下创建固定 Git worktree：
   - bare 仓库缓存目录：`<workspace_root>/_repo_cache/<repo>.git`
   - 分支 worktree 目录：`<workspace_root>/repo_worktrees/<repo>/<branch>`
3. 已存在的 worktree 只做分支校验，不自动 checkout，避免并发任务切换同一个目录。
4. Worker 提示词、请求快照和阶段事件都会记录实际分析代码目录与当前分支，便于定位。
5. 如果 Git 未安装、`repoUrl/branchName` 缺失、目录不存在、当前分支不匹配，Agent 会失败并返回明确原因。

## 使用建议

- 常用分支建议在仓库映射里维护固定 `localRepoPath`，例如每个分支一个 worktree 目录。
- 不建议多个分支共用同一个普通 clone 目录。
- `ticket_ai_workspace_root` 仍用于任务工作区和自动 worktree 根目录；`ticket_ai_local_repo_path` 不再覆盖仓库映射分支路径，避免多分支并发串扰。

## 验证

- 执行 `uv run python -m py_compile services/ticket_ai_analysis_service.py` 通过。
