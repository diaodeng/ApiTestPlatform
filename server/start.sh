#!/bin/bash
set -e
export PATH="/usr/local/bin:/app/.venv/bin:$PATH"

echo "开始安装系统依赖。。。"
sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org/debian-security|mirrors.ustc.edu.cn/debian-security|g' /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y nodejs npm wkhtmltopdf && \
    npm install --registry=https://registry.npmmirror.com jsonpath && \
    npm install --registry=https://registry.npmmirror.com jmespath

echo "系统依赖安装完成。。。"

echo "开始安装 uv..."
/usr/local/bin/pip3 install -U uv -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "uv 安装完成"

echo "开始安装应用依赖。。。"
# 安装依赖
#/usr/local/bin/pip3 install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cd /app && python -m uv sync
echo "应用依赖安装完成。。。"

# 启动fastapi应用
echo "开始启动。。。"
/app/.venv/bin/python app.py --env=prod
