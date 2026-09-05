#!/bin/bash
# 这个是给一个奇怪的环境使用的，不能修改dockerfile，构建安装的依赖运行时没有，搜易之类需要手动再次安装
set -e
export PATH="/usr/local/bin:/app/.venv/bin:$PATH"
# 统一 supervisor 子进程的运行环境，避免 Celery 退回默认 dev 配置。
export APP_ENV="${APP_ENV:-prod}"

# bullseye 已结束 LTS，镜像站 bullseye-security 池中部分依赖包（如 python3-pkg-resources）
# 文件已被清理但索引仍在，apt 安装 supervisor 会 404 失败；故运行时只装运行库，
# supervisor 为纯 Python 包，改由 pip 安装（版本较新且不依赖系统 apt 包）。
echo "开始安装系统依赖。。。"
sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org/debian-security|mirrors.ustc.edu.cn/debian-security|g' /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y libcairo2 ripgrep && \
    rm -rf /var/lib/apt/lists/*

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
