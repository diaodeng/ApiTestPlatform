# 2026-09-15 qtr-webui 子仓库瘦身：历史清理 + dist 发布流程改造

## 背景

公司 GitLab 子仓库 qtr-webui（由 `sync-subrepos.ps1` 从主仓库 `web/` 同步）体积膨胀到 **2.0 GB**：
- 历史中 dist 相关 blob 6.31 GB（88090 个文件版本），其中 `.map` 3.93 GB
- 最大元凶：`MonacoEditor.*.js.map` 单个 12.4MB × 865 个历史版本 ≈ 3.2 GB
- 另有 306 个 `master*`/`panda*` 时间戳快照 tag
- 直接后果：Jenkins 拉取 1.9GB 超时，部署失败

根因：qtr-webui 的 `.gitignore` 未排除 `dist/`，sync 脚本构建后 `robocopy dist /MIR`
+ `git add -A` 每次把全量构建产物提交进 master；Vite 产物文件名带 hash，
每次构建全量换名，git 无法增量去重，每发布一次净增 ~40MB。
（主仓库本身无此问题：`web/.gitignore` 一直排除 `web/dist/`。）

## 方案（三步）

1. **根治**：`ops/repo-cleanup.sh` 从全部历史剔除 `dist/` + 删除垃圾 tag，强推重写后历史
2. **防复发**：dist 改走 `dist-release` 单提交分支（`ops/publish-dist.sh`，每次强推覆盖，排除 `*.map`）
3. **日常不变**：仍只跑 `sync-subrepos.ps1`，其第 3 步从"镜像 dist 进影子仓库"改为"调用 publish-dist.sh 发布"

脚本唯一维护点为主仓库 `web/ops/`，随 robocopy 源码同步自动进影子仓库并入库。

## 实际执行记录

- 备份：mirror 克隆 1.9G 存于 `E:\xj\.qtr-sync\qtr-webui-backup-20260915-163652`（HEAD=1fcf6bedc）
- 删除 306 个垃圾 tag（本地+远程清零）
- `git filter-repo --path dist --invert-paths`：本地 `.git` **1.88 GiB → 6.0 MB**（重写 2.72 秒）
- 强推 master / panda / panda-newstep / yoyo（全部 forced update 成功，master 未设保护）
- 首次发布 dist-release 发现脚本 bug（旧版从未被执行过）：`find` 清空工作区把
  `.gitignore` 一并删除导致 node_modules 卷入（47355 个文件），且排除 map 的变量是死代码。
  **publish-dist.sh 重写为 plumbing 实现**（临时索引 + commit-tree，不触碰工作区，
  dist 子树直接作为根树），重发布后：根目录平铺 dist 内容、743 个文件、0 个 map
- 部署端浅克隆实测：`git clone --depth 1 -b dist-release` 仅 **25 MB**
- master 提交数 452 → 355（dist-only 提交被剔除），工作区 dist 由 gitignore 正确忽略

## 体积结果

| 项 | 清理前 | 清理后 |
|---|---|---|
| 影子仓库 `.git` | 1.88 GiB | 90 MB（含 dist-release 产物；master 源码本体 ~6 MB） |
| 远程仓库（GitLab 服务端） | ~2.0 GB | 待管理员执行 housekeeping 后回收旧对象 |
| Jenkins 完整拉取 | 超时(>10min) | 预计 <1 min |
| 部署端浅克隆 dist-release | — | 25 MB |
| 每次发布仓库增量 | +40 MB | 0（dist-release 单提交覆盖） |

## 变更文件（主仓库）

- `web/ops/publish-dist.sh`（新增）：dist → dist-release 单提交分支发布（plumbing 实现）
- `web/ops/repo-cleanup.sh`（新增）：历史清理脚本（修正旧版两处：不再恢复 dist 进 master；
  删 tag 只按 `master*`/`panda*` 两种已确认模式）
- `web/ops/REPO_CLEANUP_PLAYBOOK.md`、`web/ops/JENKINS_SHALLOW_CLONE.md`（新增）：操作手册
- `web/.gitignore`：增加 `dist/`（随同步进 qtr-webui，防止 dist 再入库）
- `sync-subrepos.ps1`：第 3 步 dist 镜像改为调用 `ops/publish-dist.sh`
- `.gitattributes`（新增）：统一行尾（`* text=auto eol=lf`，`*.ps1`/`*.bat` 用 CRLF），
  保护 .sh 脚本行尾不被 autocrlf 破坏

## 注意事项

- **其他机器/CI 的旧克隆已失效**（历史重写），必须重新 clone
- GitLab 上引用旧提交号的 MR/Compare 链接会 404，属预期
- GitLab 服务端体积下降需管理员执行 housekeeping（项目设置 → Repository → Housekeeping）
- 后续在影子仓库执行清理类脚本前，确认 `git filter-repo` 可用（本机已通过
  `uv tool install git-filter-repo` 安装至 `C:\Users\xj\.local\bin`，若不在 PATH 需先 export）
- Jenkins 若需改造（浅克隆或直拉 dist-release），见 `web/ops/JENKINS_SHALLOW_CLONE.md`
