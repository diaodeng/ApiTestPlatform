#!/bin/bash
# 这个是给一个奇怪的环境使用的，不能修改dockerfile，构建安装的依赖运行时没有，搜易之类需要手动再次安装
set -e
export PATH="/usr/local/bin:/app/.venv/bin:$PATH"
# 统一 supervisor 子进程的运行环境，避免 Celery 退回默认 dev 配置。
export APP_ENV="${APP_ENV:-prod}"

# bullseye 已于 2026-08-31 结束 LTS，USTC 镜像站的 bullseye-security 池 .deb 文件被渐进清理
# （索引仍在、下载 404），apt 事务中任一包 404 会导致整体安装失败（ripgrep 因此一直装不上，
# 日志搜索被迫降级 Python 慢速模式）。改用阿里云 debian-archive 冻结归档：仅保留 main 池，
# libcairo2/ripgrep 所需包实测完整，归档快照承诺永不清理，且 Release 无 Valid-Until 不会过期。
echo "开始安装系统依赖。。。"
# 注意：security 源必须删除而不是改指向（归档源没有 bullseye-security，指向 404 会让 apt-get update 整体失败）。
# 兼容传统 sources.list 与 deb822（debian.sources）两种格式，deb822 的 security 段按空行分块整体删除。
sed -i 's|deb.debian.org/debian|mirrors.aliyun.com/debian-archive/debian|g' /etc/apt/sources.list
sed -i '/security.debian.org/d; /bullseye-security/d' /etc/apt/sources.list 2>/dev/null || true
if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    sed -i 's|URIs: http://security.debian.org/debian-security|URIs: REMOVED|' /etc/apt/sources.list.d/debian.sources
    sed -i '/^URIs: REMOVED$/,/^$/d' /etc/apt/sources.list.d/debian.sources
    sed -i 's|URIs: http://deb.debian.org/debian|URIs: http://mirrors.aliyun.com/debian-archive/debian|' /etc/apt/sources.list.d/debian.sources
fi
# rm 不放在 && 链尾：set -e 对 && 列表中非最后命令的失败不触发退出，会让 apt 失败被静默跳过
apt-get update && apt-get install --no-install-recommends -y libcairo2 ripgrep
rm -rf /var/lib/apt/lists/*
# 安装结果必须显式可见，避免 rg 缺失后日志搜索静默降级难排查
if command -v rg >/dev/null 2>&1; then
    echo "ripgrep 安装成功：$(command -v rg)"
else
    echo "ERROR: ripgrep 安装失败，日志搜索将降级为 Python 慢速模式，大日志工单搜索会报保护阈值错误" >&2
fi
if ! ldconfig -p | grep -q libcairo; then
    echo "ERROR: libcairo2 安装失败，matplotlib 相关功能可能不可用" >&2
fi

echo "系统依赖安装完成。。。"

echo "开始安装 uv..."
/usr/local/bin/pip3 install -U uv -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "uv 安装完成"

echo "开始安装应用依赖。。。"
# 安装依赖
#/usr/local/bin/pip3 install --no-cache-dir -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cd /app && python -m uv sync --frozen
echo "应用依赖安装完成。。。"

# 启动 supervisor，由 supervisord.conf 托管 FastAPI、Celery 等进程。
# supervisor 已纳入 pyproject 依赖（supervisor==4.3.0），由上面的 uv sync 安装到 /app/.venv。
# 不再通过 apt 安装：bullseye 已结束 LTS，镜像站 security 池依赖包 404，apt 安装会失败。
echo "开始启动。。。"
echo "当前运行环境：${APP_ENV}"
exec /app/.venv/bin/supervisord -c /app/supervisord.conf
