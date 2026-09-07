# 2026-09-07 相似工单检索内存优化与监控修复

## 背景

2026-09-07 12:31 生产服务端发生重启。经 VictoriaMetrics 指标、应用日志和数据库交叉排查确认：fastapi 主进程被 cgroup 内存上限（1400MB）触发的内核 OOM Kill 杀死，supervisor 自动拉起新进程；直接诱因是 12:31:49 Agent 返回工单 AI 分析结果（raw_output 约 7.5MB），处理该响应时瞬时内存越过上限。

排查中发现三个放大点：相似工单检索全量加载向量（2664 条 × 1024 维，单次检索 GC 后仍有约 30MB 不回落）、fastapi 进程存在一次 +309MB 的不明阶跃（未归因）、观测指标存在三处缺陷导致排查被误导。本次落地其中可立即修复的部分。

## 变更内容

### 1. 相似工单检索：信号预筛 + 分页扫描（`ticket_similarity.md` 有用户说明）

- **信号预筛**：检索文本中可提取错误码 / Trace ID / Request ID 时，先按 `ticket_similarity_signal` 精确信号索引筛出候选工单，再只对候选做向量比对。生产实测带错误码检索从约 11 秒缩短到 0.2 秒内。无信号时自动退回全量扫描，不影响召回结果。可通过相似度配置 `signalPrescreenEnabled: false` 关闭（默认开启）。
- **分页扫描**：向量比对从 `yield_per` 全量迭代改为 500 条/页的独立 LIMIT/OFFSET 查询，每页处理完立即失效会话实体。旧方式下已迭代实体累积在 session 身份映射中（实测单次检索 GC 后 +31MB 不回落），新方式单次增量降到 10MB 级。
- 新增 `TicketSimilarityProfileService.extract_signal_values`：从任意文本提取归一化精确信号（复用既有 `SIGNAL_PATTERNS`）。
- 新增 `TicketDao.iter_ticket_embedding_pages`：分页迭代向量记录，支持 object_ids 白名单。

### 2. 观测缺陷修复（`memory-monitoring.md` 有用户说明）

- **cgroup v1 OOM 计数**：`qtr_cgroup_memory_events_oom_total` / `qtr_cgroup_memory_events_oom_kill_total` 此前在 cgroup v1 环境恒为 0（硬编码），导致本次排查无法用指标直接证明 OOM。现从 `memory.oom_control` 读取真实 `oom_kill` 计数。
- **任务观测器角色污染**：AI 分析、日志拉取、用例执行链路曾把共享观测器硬编码为 `role=api`，Worker 进程内执行的任务日志和 `qtr_task_*` 指标被错误标记为 `role=api`，与 fastapi 进程的指标混在同一条序列里，污染内存归因。现在统一按部署环境变量（`QTR_METRICS_ROLE`）自动判定角色。历史数据做归因时以 `pid` 为准。
- **迟到结果缓存查询**：服务重启恢复链路（lifespan 内调用 `resume_pending_tasks` → `_peek_agent_result_cache`）在事件循环内调用 `asyncio.run` 必然报错，导致重启后 Agent 已回传结果的 AI 任务被误标失败。现在事件循环内改用独立线程驱动协程。

### 3. RSS 阈值诊断快照（默认关闭，`memory-monitoring.md` 有配置说明）

针对未归因的 fastapi +309MB 阶跃，新增 `QTR_MEMORY_SNAPSHOT_ENABLED` 环境变量开关：开启后每个进程的采集线程每 10 秒检查自身 RSS，超过阈值（默认 900MB）时临时开启 tracemalloc 追踪 5 秒，把 top 分配源写入 `logs/<日期>/memory_snapshot_<role>_<时间戳>` 文件后自动关闭。默认关闭、冷却 1 小时一次，不影响现有业务。

## 变更文件

- `server/modules/ticket/dao/ticket_dao.py`：新增 `iter_ticket_embedding_pages`
- `server/modules/ticket/service/ai/ticket_embedding_service.py`：检索改造 + 预筛 + 会话逐页释放
- `server/modules/ticket/service/ai/ticket_similarity_profile_service.py`：新增 `extract_signal_values`
- `server/modules/ticket/service/ai/ticket_ai_analysis_service.py`：观测器角色修复 + 缓存查询修复
- `server/modules/ticket/service/log_pull/ticket_log_pull_service.py`、`server/module_hrm/service/runner/runner_service.py`：观测器角色修复
- `server/utils/metrics/process.py`：cgroup v1 oom_kill 读取
- `server/utils/metrics/task_memory.py`：`get_task_memory_observer` 角色语义说明（不再接受业务代码传值）
- `server/utils/metrics/collect.py`：采集线程挂接诊断快照检查
- `server/utils/metrics/memory_snapshot.py`：新增诊断快照模块
- `server/tests/test_memory_metrics.py`、`server/tests/test_ticket_embedding_service.py`：新增/更新测试

## 验证

- ruff：全部修改文件通过。
- pytest：`test_memory_metrics.py`、`test_ticket_embedding_service.py`、`test_ticket_similarity_cache.py`、`test_memory_leak_fixes.py`、`test_agent_chunk_registry.py`、`test_ticket_ai_active_lock.py` 共 66 个用例全部通过；`test_ticket_processing_metrics.py` 3 个失败经 git stash 基线对比确认为存量问题（与本次无关）。
- 生产库只读端到端：新分页逻辑与旧逻辑对同一查询向量结果完全一致（top3 分数一致）；单次检索 GC 后 RSS 增量 11MB（旧逻辑 17-31MB）；带错误码关键词预筛后检索 0.14 秒 / 1MB。
- 未执行项：未在 dev 环境做完整服务重启回归（本地无法启动完整 dev 栈）；诊断快照仅做关闭状态与单元级验证，未做真实触发验证（需部署后开启开关观察）。

## 剩余风险与建议

- fastapi 09:51 +309MB 阶跃仍未归因，建议部署本版本后开启 `QTR_MEMORY_SNAPSHOT_ENABLED=true`（阈值按现状调低，如 700MB）观察；这是下次复发前唯一的归因手段。
- 容器内存上限 1.4GB 建议提升到 2GB（运维操作，代码外）。
- 建议在 Grafana 增加 `qtr_cgroup_memory_current_bytes / qtr_cgroup_memory_max_bytes > 0.85` 持续 5 分钟的告警。
- 分页扫描 OFFSET 深翻页在向量量级达到数万条后会有性能退化，届时应接入 Qdrant（代码已支持）。
