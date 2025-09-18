@echo off
set FLUTTER_STORAGE_BASE_URL=https://mirrors.tuna.tsinghua.edu.cn/flutter
set PUB_HOSTED_URL=https://mirrors.tuna.tsinghua.edu.cn/dart-pub
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

flet build apk -v
pause
