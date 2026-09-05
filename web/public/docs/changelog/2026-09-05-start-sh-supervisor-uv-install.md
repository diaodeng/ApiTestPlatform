# 2026-09-05 - supervisor 纳入 uv 依赖管理，修复 start.sh apt 404 启动失败

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

## 变更内容

### 1. supervisor 纳入 uv 依赖管理（核心方案）

- `server/pyproject.toml` 新增 `supervisor==4.3.0`，`uv.lock` 已同步锁定。
- supervisor 是纯 Python 包，随 `start.sh` 中已有的 `uv sync --frozen` 安装到
  `/app/.venv`，venv 内自带 `supervisord` 可执行文件，无需任何额外安装步骤。
- 启动命令改为显式路径 `exec /app/.venv/bin/supervisord -c /app/supervisord.conf`，
  不依赖 PATH 解析。

### 2. apt 安装列表收敛

- `start.sh` 的 `apt-get install` 移除 `supervisor`，只保留 `libcairo2`（matplotlib 依赖）
  和 `ripgrep`（日志搜索，代码中有 Python 降级兜底）。

### 3. requirements.txt

- `server/requirements.txt` 当前为空文件（仅为兼容内部构建环境保留），无需同步。

## 影响范围

- 仅影响依赖 `start.sh` 运行时安装依赖的部署环境；正常 Dockerfile 构建的镜像
  （Dockerfile 中仍用 apt 装 supervisor）不受影响。
- supervisor 进入应用依赖集后，所有通过 `uv sync` 安装依赖的环境都会带 supervisor，
  属预期行为（包体积小，无冲突依赖）。

## 注意事项

- pip 安装的 supervisor 4.3.0 比 bullseye apt 包（4.2.2）新，`supervisord.conf` 使用的
  均为基础指令，无兼容性问题。
- 若后续升级基础镜像到 bookworm，可考虑恢复 Dockerfile 内 apt 安装，但 supervisor 留在
  uv 依赖管理中也完全可行，两种方式并存无冲突。
