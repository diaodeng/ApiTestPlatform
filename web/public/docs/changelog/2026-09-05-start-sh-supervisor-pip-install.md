# 2026-09-05 - start.sh 绕过 apt 404，supervisor 改用 pip 安装

## 问题现象

`server/start.sh` 启动时报错：

- `apt-get install supervisor` 阶段：`python3-pkg-resources_52.0.0-4+deb11u2_all.deb 404 Not Found`，导致 supervisor 安装失败。
- 后续启动阶段：`start.sh: line 29: exec: supervisord: not found`，应用无法启动。

## 根因

- 基础镜像为 `python:3.11-slim-bullseye`，Debian bullseye 已于 2026-08-31 结束 LTS 安全支持。
- USTC 镜像站的 `bullseye-security` 池开始清理过期安全更新包：`python3-pkg-resources` 的
  索引（Packages 元数据）仍存在，但 .deb 文件已被删除，`apt-get install` 因此 404 失败。
- `start.sh` 的设计是运行时手动补装系统依赖（该环境不能改 Dockerfile 重建镜像），其中
  supervisor 依赖 apt 安装，一旦 apt 失败整条启动链路中断。

## 变更内容（仅 `server/start.sh`，一行核心变化）

- supervisor 从 apt 安装列表中移除，改用系统 pip 安装（supervisor 是纯 Python 包，
  `pip install supervisor` 即可获得 `supervisord` / `supervisorctl`）：
  - `apt-get install` 只保留 `libcairo2`（matplotlib 依赖）和 `ripgrep`（日志搜索）。
  - 新增 `/usr/local/bin/pip3 install -U supervisor`（与 uv 同一安装方式、同一清华源）。
  - 启动命令由 `exec supervisord` 改为 `exec /usr/local/bin/supervisord`，显式路径，
    不依赖 PATH 解析。
- 说明：不能用 `python -m pip` 安装，因为 `uv sync` 创建的应用虚拟环境（`/app/.venv`）
  默认不带 pip；且 supervisor 装进应用 venv 会污染 `uv.lock` 管理的依赖集。

## 影响范围

- 仅影响依赖 `start.sh` 运行时安装依赖的部署环境；正常 Dockerfile 构建的镜像
  （Dockerfile 中仍用 apt 装 supervisor）不受影响。

## 注意事项

- pip 安装的 supervisor 版本（4.2.5+）比 bullseye apt 包（4.2.2）新，`supervisord.conf`
  使用的均为基础指令，无兼容性问题。
- 若后续升级基础镜像到 bookworm，可考虑恢复 apt 安装 supervisor。
