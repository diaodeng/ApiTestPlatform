# 工单 AI Agent 已登记 worktree 分支复用修复

## 背景

部分工单发起 AI 分析时，Agent 会先根据仓库映射中的 `localRepoPath` 校验当前分支；当该路径不是目标分支时，会在 `ticket_ai_workspace_root` 下派生固定 Git worktree。

如果本机曾经使用另一个工作区根目录创建过同一仓库同一分支的 worktree，而新的固定目录还不存在，旧逻辑只检查新目录是否存在，随后直接执行 `git worktree add`。Git 会因为该分支已经被其他 worktree 占用而失败：

```text
fatal: '<branch>' is already used by worktree at '<old-worktree-path>'
```

## 调整内容

1. Agent 新增 `git worktree list --porcelain` 解析逻辑。
2. 创建本地仓库派生 worktree 前，会先查找当前 Git 仓库已登记的同分支 worktree。
3. 创建远端 bare 缓存 worktree 前，也会先查找缓存仓库已登记的同分支 worktree。
4. 找到已登记目录且目录存在、当前分支校验通过时，直接复用该目录，不再重复执行 `git worktree add`。
5. 如果未找到可复用目录，仍按原固定路径创建新的 worktree。

## 影响范围

- 仅影响 `client_new` Agent 执行工单 AI 分析时的代码目录解析。
- 不改变服务端任务入库、状态流转和 AI 结果写回。
- 不会自动 checkout 已有目录，仍保持分支隔离策略。

## 排障建议

如果 Git 提示的已占用 worktree 路径已经被人工删除，但 Git 元数据尚未清理，需要在源仓库中执行 `git worktree prune` 后重试。
