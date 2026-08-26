# 自动 AI 内部网关 404 修复

## 问题

生产环境使用 `APP_ROOT_PATH=/prod-api` 时，日志拉取后的自动 AI 分析可能请求：

```text
http://127.0.0.1:8080/prod-api/qtr/agent/ai-analysis/send/{agent_code}
```

该请求是 Worker 到同机 FastAPI 的内部直连，不经过外部反向代理；把面向浏览器的 `/prod-api` 前缀带入本机路由会导致 API 进程返回 404。

## 处理

自动 AI 内部网关现在固定使用本机 FastAPI 路由 `/qtr/agent/ai-analysis/send/{agent_code}`，仅保留端口和业务路径，不再拼接 `APP_ROOT_PATH`。外部用户访问接口时仍按部署的反向代理规则使用 `/prod-api` 前缀。

## 运维注意

- 发布后需要同时重启 FastAPI、Celery Worker 和 Celery Beat，确保三个进程来自同一版本。
- 若仍出现 404，请检查生产 FastAPI 的 OpenAPI 路径是否包含 `POST /qtr/agent/ai-analysis/send/{agent_code}`，并确认 Worker 与 API 未使用不同镜像或代码目录。
- 本次排查只执行了数据库 `SELECT` 查询，没有修改任何业务数据。
