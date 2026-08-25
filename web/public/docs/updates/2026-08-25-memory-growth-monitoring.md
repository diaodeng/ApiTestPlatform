# 内存增长监控接入

- 新增 API、Celery Worker、Celery Beat 的进程级 RSS/VMS/USS、线程、子进程、句柄、连接和 Linux cgroup 内存指标。
- 新增任务开始/结束内存快照日志，覆盖 Celery 注册任务、用例执行、工单日志拉取和工单 AI 分析。
- Prometheus/VictoriaMetrics 仅使用低基数标签；任务 ID、Celery UUID 和 trace_id 保留在日志中用于归因。
- Celery 并发冲突跳过任务也会记录结束快照，指标推送增加超时和失败日志。
- 新增运维说明：[内存增长监控说明](../memory-monitoring.md)。
- 为兼容原有 vmagent 接收链路，恢复历史 CPU/内存指标的名称、标签集合和请求体格式；新增进程/cgroup/任务指标由 `QTR_METRICS_EXTENDED_ENABLED` 控制，默认关闭。
- 本次改造只增加观测能力，不调整 Celery 并发模型、不删除历史数据，也不自动重启 Worker。
