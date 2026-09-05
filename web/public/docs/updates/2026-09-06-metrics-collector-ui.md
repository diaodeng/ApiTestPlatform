# 2026-09-06 资源采集服务可视化配置

## 变更内容

资源使用情况指标（CPU、内存、进程、cgroup、任务级）的采集推送配置从环境配置文件（`.env.prod` / `.env.dev`）迁移到数据库，并在系统内提供可视化配置页面。

### 新增功能

- 新增菜单「系统监控 → 资源采集服务」：
  - 可添加多个采集服务（多个推送通道），分别指向不同 vmagent/VictoriaMetrics；
  - 每个采集服务可独立启动/停止，配置修改后 5 秒内热生效，无需重启进程；
  - 可配置推送间隔（秒）、批次条数、请求超时、job/instance/machine 标签、Basic 认证（密码加密存储）；
  - 可查看每个采集服务最近推送时间、推送状态、累计失败次数，以及各进程采集线程运行状态。
- 新增数据表 `metrics_collector_profile`，每行代表一个采集服务实例，`revision` 字段用于热生效比对。
- 新增后端模块 `server/modules/metrics/`（controller / service / dao / entity / util 分层）。

### 行为变更

- 环境配置中的 `VM_URL`、`VM_USER`、`VM_PASSWORD`、`VM_JOB`、`VM_INSTANCE`、`VM_MERCHANT`、`QTR_METRICS_EXTENDED_ENABLED` 不再参与采集链路，对应 `MetricsSettings` 配置类已删除。升级后需要在页面新建并启用采集服务，否则指标停止推送。
- `QTR_METRICS_ROLE` 环境变量保留，仍用于进程角色标签。
- 采集线程（`utils/metrics/collect.py`）重构为多通道模型：每秒采集一次原始指标，按每个启用通道独立格式化标签、攒批推送；通道配置由运行时服务周期注入，线程不直接访问数据库。
- 推送结果（成功/失败/失败次数）会回写采集服务配置行，页面可见。

## 涉及文件

- 新增：`server/modules/metrics/`（perms、controller、service×2、dao、entity、util）
- 修改：`server/server.py`（路由与权限注册、启动钩子）、`server/config/celery_app.py`、`server/config/celery_scheduler.py`（接入 runtime service）、`server/config/env.py`（删除 MetricsSettings）、`server/utils/metrics/collect.py`、`server/utils/metrics/__init__.py`
- 前端：新增 `web/src/views/monitor/metrics/`（列表页 + 弹窗组件）、`web/src/api/system/metricsCollector.js`
- 文档：更新 `web/public/docs/memory-monitoring.md`

## 注意事项

- 升级部署后若无启用的采集服务，Grafana 面板会无数据，属预期行为，需在页面启用采集服务。
- 推送间隔下限 1 秒，建议保持 5 秒；过小间隔可能打爆接收端。
- 采集/推送任何异常只记录日志和失败计数，不影响主业务。
