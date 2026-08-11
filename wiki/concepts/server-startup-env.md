# 服务启动环境说明

## 问题

在 `server/start.sh` 通过 `supervisord` 启动时，`celery beat` 可能没有拿到和 FastAPI 一致的运行环境，导致它读取到默认的 `dev` 配置，并回退到错误的数据库或 Redis 地址。

## 原因

`config/env.py` 会根据 `APP_ENV` 加载对应的 `.env.{env}` 文件。
如果 `celery beat` 启动时没有显式继承 `APP_ENV`，它会使用默认值 `dev`。

## 修复

1. `server/start.sh` 默认设置 `APP_ENV=prod`。
2. `server/supervisord.conf` 中的 FastAPI、Celery Beat、Celery Worker 统一使用同一个 `APP_ENV`。

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
