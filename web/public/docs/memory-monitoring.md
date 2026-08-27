# 内存增长监控说明

## 功能和入口

平台会在 FastAPI、Celery Worker、Celery Beat 进程中定期采集资源指标，并把任务开始/结束的内存快照写入应用日志。该功能用于定位长时间运行后内存持续增长的进程和业务链路，不会改变 Celery 并发模型，也不会自动重启进程。

VM/Prometheus 指标用于查看趋势，日志用于按任务 ID 做归因。三类进程分别使用 `role=api`、`role=celery_worker`、`role=celery_beat`。

## 配置项

现有 `VM_URL`、`VM_USER`、`VM_PASSWORD`、`VM_JOB`、`VM_INSTANCE`、`VM_MERCHANT` 配置继续生效：

- `VM_URL`：VictoriaMetrics 或 vmagent 接收 Prometheus 文本协议的地址；为空时只记录“不推送”日志。
- `VM_USER`、`VM_PASSWORD`：推送认证信息，密码不要写入日志或文档。
- `VM_JOB`：指标的 job 标签，默认 `QTR`。
- `VM_INSTANCE`：实例标签，默认 `TEST_ENV`。
- `VM_MERCHANT`：机器/商家标签，未配置时使用 `SYM_GROUP`，默认 `stable`。
- `QTR_METRICS_ROLE`：进程角色标签。Supervisor 已为 API、Beat、Worker 分别设置；未设置时默认为 `api`。
- `QTR_METRICS_EXTENDED_ENABLED`：是否发送新增进程、cgroup 和任务指标，默认 `false`。保持 `false` 时完全沿用历史 CPU/内存指标名称、标签集合和请求体格式；确认 vmagent 已支持新增指标后，设置为 `true` 才发送扩展指标。

采集线程默认每秒采集一次，按批次或 5 秒间隔推送。推送请求超时为 10 秒，失败会记录角色、HTTP 状态和失败次数。

## 主要指标

- `qtr_process_rss_bytes`：进程常驻内存。
- `qtr_process_uss_bytes`：进程独占内存，系统不支持或权限不足时可能为 0。
- `qtr_process_vms_bytes`：进程虚拟内存。
- `qtr_process_threads`、`qtr_process_children`：线程数和递归子进程数。
- `qtr_cgroup_memory_current_bytes`：Linux cgroup 当前内存用量。
- `qtr_cgroup_memory_events_oom_total`、`qtr_cgroup_memory_events_oom_kill_total`：cgroup OOM 事件累计值。
- `qtr_task_active`：当前仍在执行的观测任务数。
- `qtr_task_memory_delta_bytes`：任务结束时 RSS 相对开始快照的变化量。
- `qtr_task_completed_total`：按任务类型和状态聚合的完成数量。

旧 CPU 和内存采集结果在兼容模式下保持历史指标名和标签格式；新增进程、cgroup 和任务指标只有在 `QTR_METRICS_EXTENDED_ENABLED=true` 时发送。非数值状态字段不会发送为 Prometheus 样本。

## 日志检索

使用以下事件定位任务边界：

- `event=task_memory_start`
- `event=task_memory_finish`

结束事件包含 `task_id`、`celery_task_id`、`trace_id`、`task_family`、`queue_name`、`status`、耗时、RSS/USS 前后值、线程数和子进程数。完整任务参数、日志正文和响应正文不会写入内存诊断日志。

## 推荐排查方法

1. 先按 `role` 对比 RSS、USS 和线程数，确认增长发生在 API、Worker 还是 Beat。
2. 再按 `task_family` 查看 `qtr_task_memory_delta_bytes` 和完成数量，重点关注结束后仍持续增长的任务。
3. `celery_worker` 单独阶梯增长时，检查任务结果、线程池、HTTP/Redis 连接和子进程回收。
4. 工单日志拉取增长时，检查压缩包、解压文件、搜索子进程和线程池活动量。
5. 工单 AI 增长时，检查工作区文件、上下文大小和外部 Agent/Codex Worker 是否退出。
6. 用例执行增长时，检查并发数、结果队列、重复次数以及响应和日志规模。
7. RSS 上升但 USS 稳定时，结合 cgroup file/cache 指标判断是否为文件页缓存；不要仅凭应用日志中的 `SIGKILL` 判定 OOM。

## 已落地的内存治理（2026-08-27）

- Agent WebSocket 分片注册表（事件分片组、响应分片）超时未凑齐时由心跳任务自动清理；单组分片超过 2048 片整组丢弃。清理动作会输出 `已清理过期的事件分片组` 告警日志，可作为分片异常的信号。
- 日志拉取记录的后台轮询与管理接口使用轻量查询读取元数据，不再加载压缩正文大列；查看日志正文的接口保留全量读取。
- 工单 AI 分析的任务摘要不再回读提示词/原始输出/任务上下文大字段；AI 执行审计的响应文本与请求响应载荷写入前会做集中截断，截断处标注 `审计载荷长文本已截断` 或 `审计文本超长已截断`。
- API、Celery Beat、Celery Worker 进程注入 `MALLOC_ARENA_MAX=2`：RSS 高位横盘但 USS/对象数稳定时优先怀疑堆碎片而非泄漏，该配置可显著缓解多线程场景下空闲内存无法归还 OS 的问题。

## 注意事项

`gc.collect()` 只用于结束快照对比，不是泄漏修复。指标标签不包含任务 ID，以避免高基数时间序列；任务 ID 只出现在日志中。监控接入完成后仍需要结合实际运行曲线和任务日志进行归因，不能仅凭单次快照判定根因。
