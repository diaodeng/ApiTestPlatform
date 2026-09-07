# 内存增长监控与归因

## 目标

平台使用两层数据排查长生命周期进程的内存增长：VictoriaMetrics/Prometheus 保存低基数趋势，应用日志保存具体任务关联字段。两者通过进程角色、任务类型和时间范围关联，不把任务 ID 放入指标标签。

## 进程角色

| role | 进程 |
| --- | --- |
| `api` | FastAPI 主进程及其后台线程 |
| `celery_worker` | Celery Worker 进程 |
| `celery_beat` | Celery Beat 调度进程 |

每个进程只启动一个指标采集线程。独立进程必须使用对应的 `QTR_METRICS_ROLE`，没有设置时 API 采集器默认使用 `api`。

## 采集推送配置（数据库，热生效）

推送通道配置存储在数据库表 `metrics_collector_profile`，每行代表一个采集服务实例（推送目标 + 标签 + 间隔 + 扩展开关 + 启用状态），由「系统监控 → 资源采集服务」页面管理（模块 `server/modules/metrics/`）。

- 采集线程不直接访问数据库：`MetricsCollectorRuntimeService.start(role)` 启动线程时注入 `profile_provider` 回调（内部调用 `load_active_profiles`），线程主循环每 5 秒（`PROFILE_REFRESH_SECONDS`，首轮立即）通过回调加载启用的配置行，转换为 `CollectorProfileSnapshot` 后经 `replace_profiles` 注入并按 `revision` 比对热生效；配置修改或启停后各进程 5 秒内生效。回调抛异常时线程保留现有通道继续推送（`load_active_profiles` 数据库异常向上抛出，由线程捕获，避免空列表误清空通道）。注意：该轮询在采集线程内部自驱动，没有外部定时任务；历史版本曾因缺少轮询调用方导致配置从未注入、指标完全不推送（2026-09-06 修复）。
- 推送结果通过 `result_listener` 回调回写配置行（最近推送时间/状态/失败次数），供页面展示。
- 历史 `VM_URL`/`VM_USER`/`VM_PASSWORD`/`VM_JOB`/`VM_INSTANCE`/`VM_MERCHANT`/`QTR_METRICS_EXTENDED_ENABLED` 环境配置已不参与采集链路；`QTR_METRICS_ROLE` 仍用于角色标签。
- 每个通道独立攒批推送；扩展指标（进程/cgroup/任务）只在通道开启 `extended_enabled` 时采集和发送。
- 采集或推送异常只记日志并累计失败计数，绝不影响主业务；数据库不可用时保留现有通道配置继续推送。

## 指标口径

进程指标包括 RSS、VMS、USS（操作系统支持时）、线程数、子进程数、累计 CPU 时间、启动时间、运行时长、打开文件数和网络连接数。Linux cgroup 环境还采集当前用量、限制、anon/file/kernel/slab/swap 以及 `high`、`oom`、`oom_kill` 事件计数。注意：cgroup v1 环境的 `oom`/`oom_kill` 计数 2026-09-07 前恒为 0（读取缺陷已修复，从 `memory.oom_control` 读取）；任务观测器的 `role` 标签 2026-09-07 前在 Worker 进程内会被业务代码硬编码污染为 `api`（已修复），历史数据归因以日志中的 `pid` 为准。

任务指标包括运行中数量、完成数量、耗时、任务前后 RSS/USS、一次 GC 后 RSS、线程数和子进程数。任务指标的标签只使用 `role`、`owner_type`、`task_family`、`queue_name`、`trigger_type` 和 `status`，禁止加入 `task_id`、Celery UUID 或 trace_id。

## RSS 阈值诊断快照（2026-09-07 起，默认关闭）

用于归因"进程 RSS 一次性大幅阶跃且任务日志无法解释"的问题。`QTR_MEMORY_SNAPSHOT_ENABLED=true` 开启后，各进程采集线程每 10 秒检查自身 RSS，超过 `QTR_MEMORY_SNAPSHOT_RSS_MB`（默认 900）时临时开启 tracemalloc 追踪 5 秒，top 分配源写入 `logs/<日期>/memory_snapshot_<role>_<时间戳>` 后自动关闭，冷却 1 小时（`QTR_MEMORY_SNAPSHOT_COOLDOWN_SEC` 可调）。实现在 `utils/metrics/memory_snapshot.py`，挂在采集线程主循环节拍，不新增线程。tracemalloc 追踪期分配开销约 2 倍，只作临时诊断用，不长期开启。

## 已覆盖的业务边界

- Celery 注册任务：成功、失败、撤销、并发冲突跳过均记录开始和结束快照。
- 用例执行：报告级执行从开始到结果回写记录快照，手动终止和异常使用对应状态。
- 工单日志拉取：单条记录从阶段判断到处理结束记录快照。
- 工单 AI 分析：线程池任务从开始到 `_process_task` 结束记录快照。

## 排查流程

1. 按 `role` 对比 `qtr_process_rss_bytes`、`qtr_process_uss_bytes` 和线程数曲线。
2. 如果 RSS 和 USS 都持续增长，按任务指标的 `task_family` 和 `memory_delta_bytes` 排序，检查任务结束后是否长期不回落。
3. 如果 RSS 增长而 USS 基本稳定，优先检查文件页缓存、cgroup file/cache 和外部子进程。
4. 将指标时间窗口与日志中的 `event=task_memory_start`、`event=task_memory_finish` 对齐，再使用 `task_id`、`celery_task_id`、`trace_id` 定位具体任务。
5. 如果只有 `celery_worker` 阶梯增长，优先检查线程池复用、任务结果保留、HTTP/Redis 连接和任务子进程清理。
6. 如果只有 `api` 在工单日志或 AI 任务期间增长，优先检查压缩包、搜索管道、工作区文件和外部 Agent 生命周期；若同一时段反复出现 “等待 Agent 槽位” 且 `active_count=0`、`queue_head` 长时间不变，还要检查 Agent 分发队列是否存在陈旧队列头，以及排队中的 AI 请求是否持续持有大体积 prompt/context。
7. cgroup 的 `oom` 或 `oom_kill` 增长时，再结合容器/Pod 事件确认是否发生系统级 OOM；应用日志中的 `SIGKILL` 单独不能证明 OOM。2026-09-07 生产案例的补充判据：cgroup `current_bytes` 长时间钉死在 `max_bytes` 整数值、`file_bytes` 被内核压到最低、`swap_bytes=0` 且进程无优雅关闭日志（uvicorn 无 `Shutting down`），即使 `oom_kill` 计数为 0（v1 缺陷或 v2 未上报）也可判定为 cgroup OOM Kill；同时用 `qtr_process_uptime_seconds` 归零与 `celery_task_execution_log` 无中断区分"进程级被杀（supervisor 拉起）"与"容器整体重启"。

## 注意事项

`gc.collect()` 只用于任务结束后的诊断对比，不代表已经修复内存泄漏。USS、文件句柄和网络连接在权限不足或平台不支持时可能为 0。不要将完整任务载荷、日志正文或响应正文写入内存诊断日志。

