# 服务启动环境说明

## 问题

在 `server/start.sh` 通过 `supervisord` 启动时，`celery beat` 可能没有拿到和 FastAPI 一致的运行环境，导致它读取到默认的 `dev` 配置，并回退到错误的数据库或 Redis 地址。

## 原因

`config/env.py` 会根据 `APP_ENV` 加载对应的 `.env.{env}` 文件。
如果 `celery beat` 启动时没有显式继承 `APP_ENV`，它会使用默认值 `dev`。

## 修复

1. `server/start.sh` 默认设置 `APP_ENV=prod`。
2. `server/supervisord.conf` 中的 FastAPI、Celery Beat、Celery Worker 统一使用同一个 `APP_ENV`。
3. `supervisor` 已纳入 pyproject 依赖管理（`supervisor==4.3.0`），由 `start.sh` 中的
   `uv sync --frozen` 安装到应用虚拟环境，启动命令使用 `/app/.venv/bin/supervisord`。
   不再通过 apt 安装，原因：基础镜像 `python:3.11-slim-bullseye` 已于 2026-08-31 结束 LTS，
   镜像站的 `bullseye-security` 池中 supervisor 的依赖 `python3-pkg-resources` 的 .deb
   文件被清理（索引仍在，下载 404），导致 apt 安装失败、`supervisord` 不存在。
4. apt 源已切换到阿里云 `debian-archive` 冻结归档并删除 security 源（2026-09-10）。
   背景：bullseye EOL 后 USTC 镜像站对 security 池的清理范围扩大到 `libfreetype6`
   （`libcairo2` 的依赖），apt 事务中任一包 404 会导致整体安装失败——`libcairo2` 与
   `ripgrep` 从此一直装不上，ripgrep 缺失使日志搜索走 Python 降级路径，大日志工单搜索
   触发 `maxPythonSearchBytes` 保护阈值报错（首次实锤工单 INC00001941655）。归档源是
   EOL 后的永久冻结快照，承诺不清理，且 Release 无 `Valid-Until` 不会过期；归档源没有
   security 池，故 security 行必须整行删除（改指向会让 `apt-get update` 整体失败）。
   `start.sh` 同时兼容传统 `sources.list` 与 deb822（`sources.list.d/debian.sources`）
   两种格式，并在安装后显式自检 `rg` 与 `libcairo` 的存在性，避免再次静默降级。
   历史教训：`set -e` 对 `&&` 链中非最后一个命令的失败不触发退出，apt 失败曾被静默跳过，
   因此 `rm -rf /var/lib/apt/lists/*` 不再放在 `&&` 链尾。

## 使用方式

### 生产启动

```bash
APP_ENV=prod ./start.sh
```

### 开发启动

```bash
APP_ENV=dev ./start.sh
```

## 注意

如果你在容器外单独启动 `celery beat`，也要先设置 `APP_ENV`，否则会继续读默认环境。
