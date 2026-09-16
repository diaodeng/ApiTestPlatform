#!/usr/bin/env bash
# =====================================================================
# 发布 dist 到独立单提交分支 dist-release
#
# dist-release 分支永远只有一个提交（每次发布重写），因此仓库体积
# 恒定 = 源码历史 + 最新一份 dist，不会再膨胀。
# dist-release 的目录结构与 master 保持一致：根目录下是 dist/ 子目录
# （dist/index.html），部署端按 <仓库根>/dist/ 取文件，与旧布局完全兼容。
#
# 实现（v2，plumbing 方式）：
#   通过临时索引（GIT_INDEX_FILE）直接装载 dist 构建树并 commit-tree，
#   全程不触碰工作区、不切换分支，避免旧版"清空工作区"方案把
#   .gitignore/node_modules 一并卷进发布分支的问题。
#
# 用法（构建完成后，在仓库根目录执行）：
#   bash ops/publish-dist.sh                 # 发布 dist/ 目录内容
#   bash ops/publish-dist.sh "v1.2.3 说明"  # 自定义提交信息
#   WITH_MAP=1 bash ops/publish-dist.sh      # 包含 sourcemap（默认排除 *.map）
# =====================================================================
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

MSG="${1:-release: $(date +%Y-%m-%d_%H:%M:%S)}"

log() { printf '\033[1;36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -d dist ] && [ -n "$(ls -A dist 2>/dev/null)" ] || die "dist/ 不存在或为空，先执行 npm run build:prod"

# ---------------------------------------------------------------------
# 1. 临时索引装载 dist（-f 绕过 master 的 .gitignore 对 dist/ 的排除）
#    索引文件放在 .git 内，用相对路径避免 MSYS/Windows 路径转换问题
# ---------------------------------------------------------------------
TMPIDX=".git/dist-release-index.$$"
trap 'rm -f "$TMPIDX"' EXIT
log "装载 dist 到临时索引"
GIT_INDEX_FILE="$TMPIDX" git read-tree --empty
if [ "${WITH_MAP:-0}" = "1" ]; then
  log "包含 *.map（WITH_MAP=1）"
  GIT_INDEX_FILE="$TMPIDX" git add -f -- dist
else
  log "排除 *.map（WITH_MAP=1 可包含）"
  GIT_INDEX_FILE="$TMPIDX" git add -f -- dist ':(exclude,glob)**/*.map'
fi

# ---------------------------------------------------------------------
# 2. 生成单提交：直接用含 dist/ 前缀的完整索引树
#    （dist-release 结构与 master 一致：根目录下是 dist/ 子目录，部署端
#    按 <仓库根>/dist/ 取文件；不做子树提升，避免部署端取不到文件）
# ---------------------------------------------------------------------
TREE=$(GIT_INDEX_FILE="$TMPIDX" git write-tree)
COMMIT=$(git commit-tree "$TREE" -m "$MSG")
log "发布提交: $COMMIT"

# ---------------------------------------------------------------------
# 3. 更新本地引用并强推覆盖远程（dist-release 永远只有一个提交）
# ---------------------------------------------------------------------
git update-ref refs/heads/dist-release "$COMMIT"
log "强推 dist-release（远程旧分支被单提交替换）"
git push --force origin dist-release:dist-release
git tag -f dist-release-head "$COMMIT" >/dev/null
git push --force origin refs/tags/dist-release-head >/dev/null 2>&1 || true

log "✅ 发布完成：origin/dist-release 根目录下 = dist/（与 master 结构一致）"
log "   部署端拉取: git clone --depth 1 -b dist-release <repo-url>，取 dist/ 目录"
log "   或增量更新: git fetch --depth 1 origin dist-release && git checkout FETCH_HEAD"
