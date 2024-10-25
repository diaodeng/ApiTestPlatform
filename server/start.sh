#!/bin/bash

# 安装依赖
/usr/local/bin/pip3 install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 启动fastapi应用
echo "开始启动。。。"
python app.py --env=prod > app.log 2>&1
