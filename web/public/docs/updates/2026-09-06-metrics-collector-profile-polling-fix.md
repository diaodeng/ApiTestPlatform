# 2026-09-06 资源采集通道配置轮询缺失修复（Grafana 无数据根因）

## 问题现象

`.env.dev` 环境部署最新代码并已在「系统监控 → 资源采集服务」配置启用采集服务后，Grafana/VictoriaMetrics 中始终查不到 `memory_pressure{instance="TEST_ENV", machine="home", job="QTR"}` 等任何当前链路的指标。

## 根因

采集线程（`server/utils/metrics/collect.py` 的 `PushDataToServer`）启动时通道列表为空，采集节拍里“无通道直接返回”，而本应周期把数据库中启用的采集服务配置注入线程的 `replace_profiles` **没有任何调用方**：

- `MetricsCollectorRuntimeService` 定义了轮询间隔常量 `PROFILE_POLL_SECONDS = 5`，但全仓库无任何代码使用该常量；
- `poll_and_apply()`（加载配置并注入线程）只被注释标注“供测试或管理接口使用”，无实际调用；
- API / Celery Worker / Celery Beat 三个进程启动时都只调用了 `start(role)` 创建空线程，之后无人喂配置。

结果：数据库里的采集服务配置（`machine="home"` 一行）从未进入采集线程，每秒的采集节拍全部空转，`memory_pressure`（`MemoryCollector.snapshot()` 生成）等指标从未被推送。数据库配置本身无误。

## 修复内容

1. `server/utils/metrics/collect.py`
   - 新增常量 `PROFILE_REFRESH_SECONDS = 5`；
   - `PushDataToServer` 新增 `profile_provider` 回调（由运行时服务注入，线程保持不直接访问数据库的边界）与 `_last_profile_refresh` 时间戳；
   - 主循环每秒节拍中先执行 `_refresh_profiles_if_due()`：首轮立即刷新配置，之后每 5 秒刷新一次；回调异常只记日志并保留现有通道，不中断采集。
2. `server/modules/metrics/service/metrics_collector_runtime_service.py`
   - `start(role)` 启动线程时注入 `profile_provider = lambda: load_active_profiles(role)`，线程自驱动轮询，不再依赖外部周期任务；
   - `load_active_profiles` 数据库异常语义由“返回空列表”改为“向上抛出”：空列表会让线程误清空通道，抛出后由线程捕获并保留现有通道继续推送。

## 对用户的影响

- 部署本版本后，只要「资源采集服务」页面存在启用行，各进程最迟 5 秒内自动拿到配置并开始推送，无需重启；
- 配置新增、修改、启停依然 5 秒内热生效（行为与文档描述一致，此前实际不生效）；
- 页面上“当前进程采集线程运行状态”的 `activeProfileIds` 从空数组变为已加载的配置 ID，可作为修复生效的观察点。

## 验证

- `tests/test_memory_metrics.py` 新增 3 个回归用例（线程轮询回调并热生效、异常保留通道、运行时服务必须注入回调），10 个用例全部通过；
- 改动文件 `ruff check` 通过；
- 全量 pytest 中 27 个失败与 11 个错误经 git stash 基线对比确认为存量问题（ticket/ast 等模块），与本次改动无关。
