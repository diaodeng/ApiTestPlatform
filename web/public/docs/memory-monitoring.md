# 内存增长监控说明

## 功能和入口

平台会在 FastAPI、Celery Worker、Celery Beat 进程中定期采集资源指标，并把任务开始/结束的内存快照写入应用日志。该功能用于定位长时间运行后内存持续增长的进程和业务链路，不会改变 Celery 并发模型，也不会自动重启进程。

VM/Prometheus 指标用于查看趋势，日志用于按任务 ID 做归因。三类进程分别使用 `role=api`、`role=celery_worker`、`role=celery_beat`。

## 采集服务的可视化配置（推荐方式）

资源指标推送到哪里、以什么节奏推送、是否启用，全部在系统内可视化配置，入口：**系统监控 → 资源采集服务**。该页面支持：

- 添加多个采集服务（多个推送通道），分别指向不同的 vmagent/VictoriaMetrics 接收端；
- 随时启动与停止某个采集服务（开关生效时间最长 5 秒，无需重启任何进程）；
- 设置每个采集服务的推送间隔（秒）、批次条数、请求超时；
- 配置 job/instance/machine 标签和 Basic 认证（密码加密存储，页面不回显）；
- 查看每个采集服务最近一次推送时间、推送状态和累计失败次数；
- 查看当前进程（API / Worker / Beat）的采集线程运行状态。

配置保存或启停后自动热生效，所有采集进程会自行轮询配置（首轮立即加载，之后每 5 秒一次），修改或启停最迟 5 秒内生效，无需重启进程。启用采集服务前必须填写推送地址（`http://` 或 `https://` 开头）。推送间隔下限为 1 秒，建议保持默认 5 秒，间隔过小可能打爆接收端。停止采集服务后对应的监控面板会暂时无数据，属预期行为。

排查无数据时可依次确认：①「采集线程运行状态」中对应进程是否在运行、其 `activeProfileIds` 是否包含已启用的采集服务 ID（为空说明配置未加载，2026-09-06 之前的版本存在配置轮询缺失缺陷，进程启动后配置永远无法注入，需升级修复版本）；②数据库异常时采集线程会保留已有通道继续推送，恢复后自动重新加载，页面"最近推送状态"会反映推送成败；③后端日志中检索"采集通道启动"或"指标推送失败"可定位推送链路问题。

### 采集服务配置项说明

| 配置项 | 默认值 | 说明 |
|---|---|---|
| 服务名称 | 无 | 页面展示用，需唯一 |
| 启用推送 | 关 | 总开关，关闭后该通道停止推送 |
| 推送地址 | 无 | Prometheus 文本协议接收端点，例如 `https://vmagent.example.com/api/v1/import/prometheus` |
| 认证用户/密码 | 空 | 接收端 Basic 认证；密码加密存储，编辑时留空表示不修改 |
| job 标签 | `QTR` | 指标 `job` 标签 |
| instance 标签 | `TEST_ENV` | 指标 `instance` 标签 |
| machine 标签 | 空 | 指标 `machine` 标签，留空使用默认分组（`SYM_GROUP`，默认 `stable`） |
| 推送间隔 | 5 秒 | 两次推送之间的最小间隔，范围 1-3600 秒 |
| 批次条数 | 100 | 缓冲样本达到该条数立即推送，不必等间隔 |
| 超时 | 10 秒 | 单次推送 HTTP 请求超时，范围 1-60 秒 |
| 扩展指标 | 关 | 开启后发送进程内存、cgroup、任务级指标（见下文），样本量更大 |

## 兼容说明

历史环境配置中的 `VM_URL`、`VM_USER`、`VM_PASSWORD`、`VM_JOB`、`VM_INSTANCE`、`VM_MERCHANT`、`QTR_METRICS_EXTENDED_ENABLED` 已不再参与采集链路，采集配置统一以数据库中的采集服务为准。升级后如果系统内尚无启用的采集服务，指标会停止推送，请在「系统监控 → 资源采集服务」中新建并启用。

`QTR_METRICS_ROLE` 环境变量仍用于设置进程角色标签（API、Beat、Worker 分别为 `api`、`celery_worker`、`celery_beat`），通常无需修改。

采集线程默认每秒采集一次本机指标，按每个采集服务的批次或推送间隔推送，全部采集与推送异常都会记录日志并计入失败次数，绝不影响主业务。

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

旧 CPU 和内存采集结果在兼容模式下保持历史指标名和标签格式；新增进程、cgroup 和任务指标只有在采集服务开启「扩展指标」时发送。非数值状态字段不会发送为 Prometheus 样本。

### 指标标签分层（重要）

推送的指标按归属层级分为两类，`role` 标签的附加规则不同：

- **机器/容器级指标**（`cpu_usage_percent`、`memory_used_mb` 等机器 CPU/内存指标，以及全部 `qtr_cgroup_*`）：同一台机器上所有进程采集到的数据相同，**不带 `role` 标签**。否则同一份数据会被拆成与进程数相同的多条序列，面板聚合（sum/avg）会成倍虚高。
- **进程级指标**（`qtr_process_*`）与**任务级指标**（`qtr_task_*`）：数据为当前进程独有，**必须携带 `role` 标签**（`api` / `celery_worker` / `celery_beat`）区分进程。否则三个进程会互相覆盖同一条序列，曲线呈无规律锯齿跳变。

查询建议：看整机 CPU/内存/cgroup 时不要按 `role` 分组（这些指标没有该标签）；看进程内存与任务归因时按 `role` 分组。历史数据中 2026-08-27 之前的机器级指标可能带有 `role` 标签、进程序列可能缺失 `role`，该时间段数据存在拆分/覆盖问题，做长期趋势对比时请注意剔除。

## 指标字典

全部指标都带 `job`、`instance`、`machine`、`sensor` 标签；`machine` 即采集服务上配置的「machine 标签」，用于区分不同部署环境（如 dev 的 `home`、服务器的 `blue`）。下表数值示例取自 dev（home）环境的真实数据。

### 机器级指标（不带 role，每台机器一条序列）

| 指标 | 含义 | 示例值 | 解读 |
|---|---|---|---|
| `cpu_usage_percent` | 整机 CPU 使用率（容器内为 cgroup 配额下的使用率） | 0.13 | 单位 %。0.13 表示几乎空闲；持续 >80% 说明 CPU 饱和 |
| `cpu_limit_cores` | 可用 CPU 核数（容器内为 cgroup 配额折算核数） | 16 | 分母。使用率 = 用量 / 该配额 |
| `memory_used_mb` | 整机/容器已用内存（cgroup 视角，含文件缓存） | 578 | 容器内是 cgroup `memory.current`，含 page cache |
| `memory_limit_mb` | 内存上限（容器内为容器限额，物理机为总内存） | 15770 | 分母 |
| `memory_actual_available_mb` | 可用内存 = 上限 − 已用 | 15192 | 逼近 0 时容器有 OOM 风险 |
| `memory_pressure` | 内存压力 = 已用 / 上限 × 100% | 3.67 | 单位 %。>70 建议关注，>85 有 OOM 风险 |

### 进程级指标 `qtr_process_*`（带 role，扩展指标）

| 指标 | 含义 | 排查用途 |
|---|---|---|
| `qtr_process_rss_bytes` | 进程常驻内存（实际占用的物理内存） | **内存增长排查的第一指标**。持续单调增长（不回落）= 疑似泄漏；锯齿上升回落 = 正常负载波动 |
| `qtr_process_uss_bytes` | 进程独占内存（仅该进程使用的物理内存） | 区分「真泄漏」与「共享库占用」：RSS 涨但 USS 稳定时，增长来自共享内存或页缓存，不是该进程泄漏 |
| `qtr_process_vms_bytes` | 进程虚拟内存 | 仅参考，Python 预分配会导致虚高，一般不用 |
| `qtr_process_threads` | 线程数 | 持续增长 = 线程池/线程泄漏 |
| `qtr_process_children` | 存活子进程数 | 持续增长 = 子进程（如解压、搜索）未回收 |
| `qtr_process_cpu_seconds_total` | 进程累计 CPU 时间（秒，单调递增） | 用 `rate(qtr_process_cpu_seconds_total[5m])` 得到进程 CPU 使用率 |
| `qtr_process_open_files` | 打开文件句柄数 | 持续增长 = 文件/连接泄漏 |
| `qtr_process_connections` | 网络连接数 | 持续增长 = 连接未释放 |
| `qtr_process_uptime_seconds` | 进程运行时长 | 判断进程是否重启过（归零即重启） |
| `qtr_process_start_time_seconds` | 进程启动时刻（Unix 秒） | 同上 |

### 容器内存明细 `qtr_cgroup_memory_*`（不带 role，扩展指标）

| 指标 | 含义 | 排查用途 |
|---|---|---|
| `qtr_cgroup_memory_current_bytes` | cgroup 当前内存总量 | 对应 `memory_used_mb` 的字节精确值 |
| `qtr_cgroup_memory_max_bytes` | cgroup 内存上限 | 分母；`max` 值（无限制）时不上报 |
| `qtr_cgroup_memory_anon_bytes` | 匿名内存（Python 对象、堆） | **持续增长 = 应用真实泄漏**，这部分无法被内核回收 |
| `qtr_cgroup_memory_file_bytes` | 文件页缓存 | 可被内核随时回收，增长通常无害；RSS 高但 anon 稳定时优先看这里 |
| `qtr_cgroup_memory_kernel_bytes` | 内核栈等内核内存 | 异常增长多与 socket/挂载有关 |
| `qtr_cgroup_memory_slab_bytes` | 内核 slab 缓存（dentry/inode） | 大量小文件操作后会增长，可回收 |
| `qtr_cgroup_memory_swap_bytes` | 使用的交换分区 | >0 说明物理内存吃紧，系统开始换页 |
| `qtr_cgroup_memory_events_high_total` | 内存使用触及 high 水位次数 | 触发内核回收，增长说明内存紧张 |
| `qtr_cgroup_memory_events_oom_total` | 发生 OOM（内存超限）次数 | 增长 = 容器内存超限被限制 |
| `qtr_cgroup_memory_events_oom_kill_total` | OOM Killer 杀死进程次数 | **增长 = 有进程被强杀**，结合应用日志定位被杀进程 |

### 任务级指标 `qtr_task_*`（带 role 与任务维度标签，扩展指标）

额外标签：`task_family`（任务类型）、`queue_name`（队列）、`owner_type`（业务域）、`trigger_type`（触发方式 scheduler/once/background）、`status`（success/failed/running 等）。

| 指标 | 含义 | 排查用途 |
|---|---|---|
| `qtr_task_active` | 当前正在执行的任务数 | 突增后长时间不回落 = 任务卡住 |
| `qtr_task_completed_total` | 按任务类型/状态聚合的完成数（Counter） | 用 `rate(...[5m])` 看任务吞吐；failed 增长快 = 任务异常 |
| `qtr_task_duration_ms` | 任务耗时（毫秒，最后一次） | 结合 task_family 看哪类任务变慢 |
| `qtr_task_memory_before_bytes` / `_after_bytes` | 任务开始/结束时进程 RSS | 差值即任务内存影响 |
| `qtr_task_memory_delta_bytes` | 任务前后 RSS 变化量 | **定位高内存任务的关键指标**：按 task_family 聚合取 top，即「哪类任务吃内存」 |
| `qtr_task_memory_after_gc_bytes` | 任务结束后 GC 一次的 RSS | delta 高但 after_gc 回落 = 正常大对象分配；after_gc 仍高 = 内存未释放，疑似泄漏 |
| `qtr_task_threads` / `qtr_task_children` | 任务结束时的线程数/子进程数 | 异常增长 = 任务泄漏线程/子进程 |

## 统计与排查方法（Grafana / PromQL）

数据源选择 vmagent 对应的 VictoriaMetrics，环境过滤统一用 `machine="home"`（dev）或 `machine="blue"`（服务器），下例以 dev 为例。

### 第一步：确认压力在哪个层面（机器级）

```promql
# 内存压力曲线（>85% 紧急）
memory_pressure{machine="home"}

# 整机 CPU
cpu_usage_percent{machine="home"}
```

### 第二步：定位是哪个进程（进程级）

```promql
# 三个进程的 RSS 对比（MB）——谁在涨一目了然
qtr_process_rss_bytes{machine="home"} / 1024 / 1024

# 最近 1 小时内存增长率（bytes/s），正值持续增长即疑似泄漏
deriv(qtr_process_rss_bytes{machine="home"}[1h])

# 进程 CPU 使用率（单核百分比）
rate(qtr_process_cpu_seconds_total{machine="home"}[5m]) * 100

# 线程/句柄/连接泄漏检查
qtr_process_threads{machine="home"}
qtr_process_open_files{machine="home"}
qtr_process_connections{machine="home"}
```

### 第三步：判断是真泄漏还是页缓存（cgroup 级）

```promql
# 匿名内存（应用真实占用）趋势——只有这条涨才是应用泄漏
qtr_cgroup_memory_anon_bytes{machine="home"} / 1024 / 1024

# 文件页缓存趋势——这条涨不用慌，内核可回收
qtr_cgroup_memory_file_bytes{machine="home"} / 1024 / 1024

# OOM 与换页
increase(qtr_cgroup_memory_events_oom_kill_total{machine="home"}[24h])
qtr_cgroup_memory_swap_bytes{machine="home"}
```

### 第四步：定位是哪类任务吃资源（任务级）

```promql
# 各任务类型的内存增量 Top（按 task_family 排序）——直接回答"什么任务导致资源高"
topk(10, avg_over_time(qtr_task_memory_delta_bytes{machine="home"}[1h]))

# 哪类任务最耗 CPU 时间
topk(10, avg_over_time(qtr_task_duration_ms{machine="home"}[1h]))

# 任务吞吐与失败率
sum by (task_family, status) (rate(qtr_task_completed_total{machine="home"}[10m]))

# 任务结束后内存仍未释放的类型（after_gc 仍高于 before 的均值差）
avg_over_time(qtr_task_memory_after_gc_bytes{machine="home"}[1h])
- ignoring(status, trigger_type, owner_type, queue_name)
  avg_over_time(qtr_task_memory_before_bytes{machine="home"}[1h])
```

### 常见结论对照表

| 现象 | 结论 | 处理方向 |
|---|---|---|
| `qtr_process_rss_bytes` 单调上涨不回落，`qtr_process_uss_bytes` 同步上涨 | 进程级内存泄漏 | 按第四步找 task_family，结合 `event=task_memory_finish` 日志定位具体任务 |
| RSS 上涨但 USS 平稳、`qtr_cgroup_memory_file_bytes` 上涨 | 文件页缓存，非泄漏 | 无需处理，内核按需回收 |
| `memory_pressure` 高但 `anon_bytes` 平稳 | 缓存占用虚高 | 可忽略或调低页缓存 |
| `qtr_process_cpu_seconds_total` 的 rate 突增 | 某进程 CPU 高 | 结合任务 duration 与 task_active 定位当时在跑的任务 |
| `oom_kill_total` 增长 | 容器 OOM 杀进程 | 结合内核日志与应用日志找被杀时间点的任务 |
| `threads`/`open_files`/`connections` 单调涨 | 线程/句柄泄漏 | 检查对应进程的线程池与连接管理 |

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
