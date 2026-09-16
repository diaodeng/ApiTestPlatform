#!/usr/bin/env bash
# =====================================================================
# GitLab 仓库历史清理：从所有分支/标签中剔除 dist/ 与时间戳快照 tag
#
# 目标：仓库从 ~2.0 GB 降到 ~10 MB，使 Jenkins 普通拉取不再超时。
#
# ⚠️ 本脚本会重写全部提交历史并 force push，执行前必须通读
#    ops/REPO_CLEANUP_PLAYBOOK.md，并确认备份已完成。
#
# 用法（在仓库根目录执行）：
#   bash ops/repo-cleanup.sh            # 实际执行（重写 + 强推）
#   DRY_RUN=1 bash ops/repo-cleanup.sh  # 演练：只做备份与统计，不重写
#
# 与旧版的差异：不再把 dist 恢复进 master（步骤5 删除）——
# dist 完全交给 dist-release 单提交分支发布，master 彻底不再跟踪 dist，
# 否则 .gitignore 对已跟踪文件不生效，下次同步 dist 又会入库，清理白做。
# =====================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${REPO_DIR}-backup-$(date +%Y%m%d-%H%M%S)"
DRY_RUN="${DRY_RUN:-0}"
cd "$REPO_DIR"

log()  { printf '\n\033[1;36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------
# 0. 前置检查
# ---------------------------------------------------------------------
log "0/6 前置检查"

command -v git-filter-repo >/dev/null 2>&1 || \
  die "git filter-repo 不可用。安装方式（任选其一）：
  A. pip 安装（需 Python 3.8+）: pip install git-filter-repo
  B. 单文件安装（无需 Python 包管理器）:
     curl -L -o ~/bin/git-filter-repo https://raw.githubusercontent.com/newren/git-filter-repo/main/git-filter-repo
     chmod +x ~/bin/git-filter-repo   # 确保 ~/bin 在 PATH 中"

git diff --quiet && git diff --cached --quiet || \
  die "工作区有未提交改动，先提交或 stash 后再执行"

[ "$(git status --porcelain | wc -l)" -eq 0 ] || \
  die "工作区不干净，先处理未跟踪文件"

if [ -n "$(git stash list)" ]; then
  die "存在 stash：$(git stash list | head -3)
  filter-repo 重写后 stash 可能失效，请先处理（git stash drop 或导出 patch）后再执行"
fi

# ---------------------------------------------------------------------
# 1. 备份（mirror 裸克隆，含所有分支/标签/引用）
# ---------------------------------------------------------------------
log "1/6 备份到 ${BACKUP_DIR}（mirror 克隆，约 2GB，耗时取决于磁盘）"
git clone --mirror "http://gitlab.rta-os.com/jie.xiong/qtr-webui.git" "$BACKUP_DIR" \
  || die "备份克隆失败，中止（也可直接复制本地 .git: cp -r .git ${BACKUP_DIR}.git）"
log "备份完成：$(du -sh "$BACKUP_DIR" | cut -f1)"

[ "$DRY_RUN" = "1" ] && { log "DRY_RUN 模式：到此为止，未做任何修改"; exit 0; }

# ---------------------------------------------------------------------
# 2. 清理垃圾 tag：master2024xxxx / panda2024xxxx 时间戳快照 tag（本地+远程）
#    只删两类已确认的时间戳模式，不再用宽泛的 v[0-9]*-[0-9]* 规则，避免误删
# ---------------------------------------------------------------------
log "2/6 删除时间戳快照 tag（本地与远程）"
GARBAGE_TAGS=$(git tag -l 'master[0-9]*' 'panda[0-9]*' 2>/dev/null || true)
if [ -n "$GARBAGE_TAGS" ]; then
  echo "$GARBAGE_TAGS" | xargs git tag -d >/dev/null
  # 远程分批删除，避免命令行过长
  echo "$GARBAGE_TAGS" | xargs -n 50 git push origin --delete >/dev/null 2>&1 || \
    warn "部分远程 tag 删除失败，可稍后手动清理"
  log "已删除 $(echo "$GARBAGE_TAGS" | wc -l) 个垃圾 tag"
else
  log "未发现匹配的垃圾 tag，跳过"
fi

# ---------------------------------------------------------------------
# 3. filter-repo 重写历史：剔除所有分支/标签中的 dist/
# ---------------------------------------------------------------------
log "3/6 filter-repo 重写历史（剔除 dist/，449 个提交，预计 1~5 分钟）"
git filter-repo --path dist --invert-paths --force

log "filter-repo 完成，本地仓库现状："
du -sh .git | awk '{print "  .git = " $1}'

# ---------------------------------------------------------------------
# 4. 恢复 origin（filter-repo 出于安全会移除 remote，连同分支跟踪配置）
# ---------------------------------------------------------------------
log "4/6 恢复 remote origin 与分支跟踪"
git remote add origin "http://gitlab.rta-os.com/jie.xiong/qtr-webui.git"
for BR in master panda panda-newstep yoyo; do
  git branch --set-upstream-to="origin/$BR" "$BR" 2>/dev/null \
    || warn "分支 $BR 的 upstream 设置失败（分支不存在时忽略）"
done

# ---------------------------------------------------------------------
# 5. .gitignore 增加 dist/（master 从此不再提交 dist）
#    注意：不再从备份恢复 dist 到 master——旧版做法会让 dist 重新被跟踪，
#    .gitignore 对已跟踪文件不生效，sync 脚本一跑 dist 又会入库。
#    部署所需 dist 由 ops/publish-dist.sh 发布到 dist-release 单提交分支。
# ---------------------------------------------------------------------
log "5/6 .gitignore 增加 dist/"
grep -q '^dist/$' .gitignore || printf '\n# 构建产物不再入库，通过 dist-release 分支发布\ndist/\n' >> .gitignore
git add .gitignore
git commit -m "chore: gitignore 增加 dist/" || warn "gitignore 已包含 dist/，跳过提交"

# ---------------------------------------------------------------------
# 6. Force push 全部分支与剩余 tag
# ---------------------------------------------------------------------
log "6/6 强推所有分支与 tag 到 origin"
for BR in master panda panda-newstep; do
  git push --force origin "$BR" || die "推送 $BR 失败"
done
# yoyo 只存在于远程，本地重写后无对应分支；用 refspec 直接推重写后的对象
git push --force origin "refs/remotes/origin/yoyo:refs/heads/yoyo" 2>/dev/null \
  || warn "yoyo 分支推送失败，请检查（若该分支已废弃可忽略）"
git push --force origin --tags

log "✅ 清理完成。验证：git count-objects -vH"
git count-objects -vH | grep -E 'size-pack|count'
warn "提醒：其他机器上的旧克隆需重新 clone；Jenkins 任务无需浅克隆也能秒级拉取了"
