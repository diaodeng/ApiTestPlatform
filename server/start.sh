#!/bin/bash

echo "开始安装系统依赖。。。"
sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org/debian-security|mirrors.ustc.edu.cn/debian-security|g' /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y nodejs npm && \
    npm install --registry=https://registry.npmmirror.com jsonpath && \
    npm install --registry=https://registry.npmmirror.com jmespath

echo "系统依赖安装完成。。。"

echo "开始安装应用依赖。。。"
# 安装依赖
/usr/local/bin/pip3 install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "应用依赖安装完成。。。"

# 启动fastapi应用
echo "开始启动。。。"
python app.py --env=prod > app.log 2>&1
