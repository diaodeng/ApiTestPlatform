# 工单 AI Agent 分支隔离说明

## 背景

工单 AI 分析由 `client_new` Agent 调用 `codex exec` 读取本地代码。不同工单可能映射到不同分支，如果多个分析任务共享同一个本地仓库目录，运行期间的分支状态会互相影响，导致 Codex 读取到错误分支代码。

## 调整内容

1. Agent 执行前优先检查仓库映射下发的 `localRepoPath`，如果该目录当前 Git 分支等于映射的 `branchName`，则直接使用该目录。
2. 如果 `localRepoPath` 当前分支与 `branchName` 不一致，Agent 会基于这个本地仓库创建或复用固定 Git worktree：
   - 本地派生 worktree 目录：`<workspace_root>/repo_worktrees/local/<source_repo>/<branch>`
   - 创建命令在 `localRepoPath` 下执行，因此复用原项目 `.git/config`、remote 和本地 Git 凭据。
3. 如果映射未配置 `localRepoPath`，Agent 才会按 `repoUrl + branchName` 创建或复用 bare 缓存仓库和固定 worktree：
   - bare 仓库缓存目录：`<workspace_root>/_repo_cache/<repo>.git`
   - 分支 worktree 目录：`<workspace_root>/repo_worktrees/<repo>/<branch>`
4. 已存在的 worktree 只做分支校验，不自动 checkout，避免并发任务切换同一个目录。
5. Worker 提示词、请求快照和阶段事件都会记录实际分析代码目录与当前分支，便于定位。
6. 如果 Git 未安装、`branchName` 缺失、自动 worktree 创建失败，Agent 会失败并返回明确原因。

## 使用建议

- 常用分支建议在仓库映射里维护固定 `localRepoPath`，例如每个分支一个 worktree 目录。
- 不建议多个分支共用同一个普通 clone 目录。
- 如果历史映射把多个版本都指向同一个 `localRepoPath`，现在不会再直接使用错误分支目录；Agent 会从该本地仓库派生按分支隔离的 worktree。
- `ticket_ai_workspace_root` 仍用于任务工作区和自动 worktree 根目录；`ticket_ai_local_repo_path` 不再覆盖仓库映射分支路径，避免多分支并发串扰。

## 验证

- 执行 `uv run python -m py_compile services/ticket_ai_analysis_service.py` 通过。
