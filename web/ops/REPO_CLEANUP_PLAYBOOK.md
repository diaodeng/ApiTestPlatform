# qtr-webui 仓库瘦身与发布流程改造手册

## 背景

| 项 | 值 |
|---|---|
| `.git` 体积 | **2.0 GB**（21 个 pack，1.88 GiB） |
| 工作区（不含 .git） | 51 MB（其中 dist 41 MB） |
| 历史大 blob | dist 相关 6.31 GB（88090 个文件版本），其中 `.map` 3.93 GB |
| 大头 | `MonacoEditor.*.js.map` 单个 12.4 MB × 865 个历史版本 = 3.2 GB |
| 垃圾 tag | 305 个（302 个 `master*` + 3 个 `panda*` 时间戳快照） |
| 直接后果 | Jenkins `git fetch +refs/heads/*` 拉 1.9 GB，10 分钟超时，部署失败 |

根因：`.gitignore` 未排除 `dist/`，449 个提交中 321 个提交了构建产物；
Vite 产物文件名带 hash（`MonacoEditor.D9f4J3Bl.js.map` → 下次构建换名），
git 无法增量去重，每发布一次净增 ~40MB。

> 膨胀只发生在 qtr-webui（公司子仓库）。主仓库 web/.gitignore 一直排除
> `web/dist/`，主仓库本身没有这个问题；dist 是被 sync-subrepos.ps1 的
> `robocopy dist /MIR` + `git add -A` 每次带进影子仓库的。

## 方案总览

```
① 止血（当天）   Jenkins 配浅克隆 depth=1        → 恢复部署，等不了清理
② 根治（一次）   repo-cleanup.sh 清历史          → 仓库 2.0GB → ~10 MB
③ 防复发（长期） dist 走 dist-release 单提交分支  → 体积终身恒定 ~15MB
```

新流程下：
- **master** = 源码 + 配置 + `ops/` 脚本（~10 MB），`.gitignore` 排除 `dist/`
- **dist-release** = 单提交分支，根目录即可部署的 dist 内容，每次发布强推覆盖
- **Jenkins** = 浅克隆拉 master 构建镜像（Dockerfile 本就多阶段自建 dist），或直接拉 dist-release 部署

日常入口不变：仍然只跑 `sync-subrepos.ps1`，它内部完成构建 + 源码提交 +
调用 `ops/publish-dist.sh` 发布 dist-release。

## 第一阶段：立即止血（Jenkins 浅克隆）

见 [JENKINS_SHALLOW_CLONE.md](JENKINS_SHALLOW_CLONE.md) 第一节，加
`CloneOption depth=1, shallow=true, timeout=20`，拉取量 1.9GB → 20MB。
此步骤与后续清理无依赖，可先做。

## 第二阶段：历史清理（一次性，约 20~40 分钟）

前置：安装 git-filter-repo（任选其一）：

```bash
# A. pip/uv 安装
uv tool install git-filter-repo   # 或 pip install git-filter-repo

# B. 单文件安装（无 Python 包管理器）
mkdir -p ~/bin && curl -L -o ~/bin/git-filter-repo \
  https://raw.githubusercontent.com/newren/git-filter-repo/main/git-filter-repo
chmod +x ~/bin/git-filter-repo
export PATH="$HOME/bin:$PATH"     # 加入 ~/.bashrc
```

⚠️ **执行前确认**：
1. 工作区干净、无 stash（脚本会强制检查并中止）。
2. 重写会 force push master/panda/panda-newstep/yoyo，其他机器的克隆将失效。
3. GitLab master 若为保护分支，需管理员临时放开 force push 权限。

执行（先演练再实操，脚本从主仓库 `web/ops/` 随源码同步过来后在影子仓库执行）：

```bash
cd ~/.qtr-sync/qtr-webui    # 影子仓库（位置以 QTR_SYNC_ROOT 配置为准）
DRY_RUN=1 bash ops/repo-cleanup.sh   # 演练：只备份+统计
bash ops/repo-cleanup.sh             # 实操：备份→清tag→重写→强推
```

脚本自动完成 6 步：前置检查 → mirror 备份（`../qtr-webui-backup-*`）→
删 305 个垃圾 tag → `filter-repo --path dist --invert-paths` → 恢复 origin →
`.gitignore` 加 `dist/` → 强推全部分支。

**回滚**：任何异常时，备份目录就是完整裸仓库，直接换回：

```bash
rm -rf .git && git clone ../qtr-webui-backup-YYYYMMDD-HHMMSS .  # 或整目录替换
```

## 第三阶段：日常发布（防复发）

日常无需记忆额外命令，`sync-subrepos.ps1` 已内置；手动发布时才用：

```bash
npm run build:prod
bash ops/publish-dist.sh              # dist → dist-release 单提交强推
git push origin master                # 源码正常提交（不再含 dist）
```

细节：
- `publish-dist.sh` 默认**排除 `*.map`**（sourcemap 占 25.6MB/41MB），
  需要 map 时 `WITH_MAP=1 bash ops/publish-dist.sh`
- dist-release 永远只有一个提交，远程体积不随发布次数增长
- 部署端取产物：
  ```bash
  git clone --depth 1 -b dist-release http://gitlab.rta-os.com/jie.xiong/qtr-webui.git
  ```

## 预期结果

| 指标 | 现状 | 清理后 | 新流程长期 |
|---|---|---|---|
| 远程仓库 | 2.0 GB | ~10 MB | ~15 MB 恒定 |
| Jenkins 完整拉取 | 超时(>10min) | <1 min | <1 min |
| Jenkins 浅拉取 | ~20 MB | ~10 MB | ~15 MB |
| 每次发布仓库增量 | +40 MB | — | **0**（单提交覆盖） |

## 注意事项

1. **其他克隆失效**：历史重写后，所有其他机器/CI 的旧 clone 必须重新 clone
   （旧 clone 里还有 1.9GB 历史，且 push 会被拒绝）
2. **MR/Compare 引用旧提交号**：GitLab 上引用被重写提交的链接会 404，属预期
3. **GitLab 侧回收**：强推后 GitLab 服务端旧对象不会立刻删除，体积下降要在
   管理员执行 housekeeping（项目设置 → Repository → Housekeeping，或等自动触发）
   后才体现；`git count-objects` 看的是本地，本地立即生效
4. **脚本维护**：两个脚本以主仓库 `web/ops/` 为唯一维护点，随
   sync-subrepos.ps1 的 robocopy 自动同步进影子仓库并入库，不要直接改影子仓库里的副本
